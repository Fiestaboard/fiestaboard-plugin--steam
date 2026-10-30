"""Steam activity, friends and achievements for any configured Steam profile."""
import os
import re
import threading

from src.plugins.base import PluginBase, PluginResult

from . import steam_api
from .display import clean, layout
from .steam_api import SteamError, parse_profile

STATS_TTL = 300
STATES = {0: "Offline", 1: "Online", 2: "Busy", 3: "Away", 4: "Snooze", 5: "Looking to trade", 6: "Looking to play"}


def number(value):
    """Return a nonnegative numeric value, preserving unknown as None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < 10**12:
        return value
    return None


def game_id(value):
    if isinstance(value, bool):
        return None
    text = str(value or "")
    return int(text) if text.isdigit() and 0 < int(text) < 2**32 else None


def records(value):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise SteamError("Steam returned incomplete data. Please try again later.")
    return value


def favorite_ids(value):
    return list(dict.fromkeys(x for x in re.split(r"[\s,]+", str(value or "").strip()) if x))


def game_list(client, sid, recent=False):
    method = "GetRecentlyPlayedGames" if recent else "GetOwnedGames"
    params = {"steamid": sid, "count": 0} if recent else {"steamid": sid, "include_appinfo": True, "include_played_free_games": True}
    result = client.get("IPlayerService", method, 1, params, STATS_TTL).get("response")
    key = "total_count" if recent else "game_count"
    if not isinstance(result, dict) or number(result.get(key)) is None:
        raise SteamError("Game details or playtime are private or unavailable.")
    games = records(result.get("games", []))
    if result[key] != len(games) or any(not game_id(g.get("appid")) for g in games):
        raise SteamError("Steam returned incomplete game data.")
    return games


def summaries(client, ids, ttl):
    result = client.get("ISteamUser", "GetPlayerSummaries", 2, {"steamids": ",".join(ids)}, ttl).get("response")
    if not isinstance(result, dict):
        raise SteamError("Steam returned incomplete profile data.")
    players = records(result.get("players"))
    if {str(p.get("steamid")) for p in players} != set(ids):
        raise SteamError("Some Steam profiles are missing or unavailable.")
    return players


def friends_data(client, sid, favorites, ttl):
    if favorites:
        ids = favorites
    else:
        result = client.get("ISteamUser", "GetFriendList", 1, {"steamid": sid, "relationship": "friend"}, 900).get("friendslist")
        if not isinstance(result, dict):
            raise SteamError("Friends list is private or unavailable.")
        friends = records(result.get("friends"))
        ids = list(dict.fromkeys(str(f["steamid"]) for f in friends))
    output = []
    for start in range(0, len(ids), 100):
        for player in summaries(client, ids[start:start + 100], ttl):
            state = player.get("personastate")
            if state not in STATES:
                raise SteamError("Some friends' activity is unavailable.")
            playing = bool(player.get("gameid"))
            output.append({"steam_id": str(player["steamid"]), "name": clean(player.get("personaname")) or "Steam player",
                           "status": "In game" if playing else STATES[state], "game": clean(player.get("gameextrainfo")) if playing else "",
                           "is_online": state > 0 or playing, "is_playing": playing})
    output.sort(key=lambda p: (not p["is_playing"], not p["is_online"], p["name"].casefold(), p["steam_id"]))
    return output


def achievement_data(client, sid, appid):
    result = client.get("ISteamUserStats", "GetPlayerAchievements", 1, {"steamid": sid, "appid": appid, "l": "english"}, STATS_TTL).get("playerstats")
    if not isinstance(result, dict) or result.get("success") is not True:
        raise SteamError("Achievements are private, unsupported by this game, or unavailable.")
    achievements = records(result.get("achievements"))
    if any(a.get("achieved") not in (0, 1) or not isinstance(a.get("apiname"), str) for a in achievements):
        raise SteamError("Steam returned incomplete achievement data.")
    unlocked = [a for a in achievements if a["achieved"] == 1]
    latest = max(unlocked, key=lambda a: number(a.get("unlocktime")) or 0, default={})
    latest_name = clean(latest.get("name"))
    schema_status = ""
    try:
        schema = client.get("ISteamUserStats", "GetSchemaForGame", 2, {"appid": appid, "l": "english"}, 86400)
        definitions = records(schema["game"].get("availableGameStats", {}).get("achievements", []))
        names = {a["name"]: clean(a.get("displayName")) for a in definitions}
        latest_name = names.get(latest.get("apiname"), latest_name)
    except (SteamError, KeyError, TypeError, AttributeError):
        schema_status = "Achievement names unavailable; counts are available."
    total = len(achievements)
    return {"game_name": clean(result.get("gameName")), "achievements_available": True,
            "achievements_unlocked": len(unlocked), "achievements_total": total,
            "achievements_remaining": total - len(unlocked),
            "achievement_percent": round(100 * len(unlocked) / total) if total else None,
            "achievement_summary": f"{len(unlocked)} OF {total} UNLOCKED" if total else "NO ACHIEVEMENTS",
            "latest_achievement": latest_name or clean(latest.get("apiname")),
            "latest_unlock_time": number(latest.get("unlocktime")), "achievements_status": schema_status or "Available"}


class SteamPlugin(PluginBase):
    """One selected profile per named instance; no special owner-only features."""

    @property
    def plugin_id(self):
        return "steam"

    def __init__(self, manifest):
        super().__init__(manifest)
        self._client = None
        self._client_key = None
        self._lock = threading.RLock()

    def on_config_change(self, old_config, new_config):
        with self._lock:
            self._client = None
            self._client_key = None

    def validate_config(self, config):
        errors = []
        if not str(config.get("api_key") or os.getenv("STEAM_API_KEY", "")).strip():
            errors.append("Steam API key is required. Create one at steamcommunity.com/dev/apikey.")
        try:
            parse_profile(config.get("profile"))
        except (SteamError, ValueError):
            errors.append("Enter a 17-digit Steam ID or a Steam Community profile URL.")
        refresh = config.get("refresh_seconds", 60)
        if type(refresh) is not int or not 30 <= refresh <= 3600:
            errors.append("Refresh interval must be between 30 and 3600 seconds.")
        if config.get("display_mode", "now_playing") not in ("now_playing", "friends", "achievements"):
            errors.append("Choose Now Playing, Friends, or Achievement Chase.")
        selected = config.get("game_id", 0)
        if selected not in (None, "", 0, "0") and game_id(selected) is None:
            errors.append("Game ID must be a positive Steam app ID, or 0 for automatic selection.")
        if any(not re.fullmatch(r"\d{17}", sid) for sid in favorite_ids(config.get("favorite_friends"))):
            errors.append("Favorite friends must be 17-digit Steam IDs separated by commas.")
        return errors

    def fetch_data(self):
        with self._lock:
            config = dict(self.config)
            errors = self.validate_config(config)
            if errors:
                return PluginResult(available=False, error=" ".join(errors))
            key = str(config.get("api_key") or os.getenv("STEAM_API_KEY", "")).strip()
            if self._client is None or self._client_key != key:
                self._client = steam_api.SteamClient(key)
                self._client_key = key
            try:
                data = self._collect(self._client, config)
            except (SteamError, ValueError) as exc:
                return PluginResult(available=False, error=str(exc))
            except (KeyError, TypeError, AttributeError):
                return PluginResult(available=False, error="Steam returned incomplete profile data. Please try again later.")
            board = self.board
            rows, cols = (board.rows, board.cols) if board else (6, 22)
            lines = layout(data, config.get("display_mode", "now_playing"), rows, cols)
            data.update({f"line_{n + 1}": lines[n].strip() if n < len(lines) else "" for n in range(6)})
            return PluginResult(available=True, data=data, formatted_lines=lines)

    def _collect(self, client, config):
        sid = client.resolve_profile(config["profile"])
        ttl = config.get("refresh_seconds", 60)
        player = summaries(client, [sid], ttl)[0]
        playing = bool(player.get("gameid"))
        data = {
            "steam_id": sid, "player_name": clean(config.get("display_name") or player.get("personaname")) or "Steam player",
            "profile_url": f"https://steamcommunity.com/profiles/{sid}/",
            "status": "In game" if playing else STATES.get(player.get("personastate"), "Unavailable"),
            "is_playing": playing, "current_game": clean(player.get("gameextrainfo")) if playing else "",
            "current_game_id": game_id(player.get("gameid")), "game_id": None, "game_name": "",
            "playtime_hours": None, "recent_hours": None, "game_recent_hours": None, "library_count": None,
            "playtime_status": "Unavailable", "recent_status": "Unavailable", "recent_games": [],
            "friends": [], "friends_online": None, "friends_playing": None, "friends_total": None,
            "friends_available": False, "friends_status": "Unavailable",
            "friends_scope": "Favorites" if config.get("favorite_friends") else "All friends",
            "achievements_available": False, "achievements_unlocked": None, "achievements_total": None,
            "achievements_remaining": None, "achievement_percent": None, "achievement_summary": "STATS UNAVAILABLE",
            "latest_achievement": "", "latest_unlock_time": None, "achievements_status": "No game selected or visible.",
        }
        recent, owned = [], []
        try:
            recent = game_list(client, sid, recent=True)
            for game in recent:
                minutes = number(game.get("playtime_2weeks"))
                lifetime = number(game.get("playtime_forever"))
                data["recent_games"].append({"appid": game["appid"], "name": clean(game.get("name")),
                    "recent_hours": round(minutes / 60, 1) if minutes is not None else None,
                    "playtime_hours": round(lifetime / 60, 1) if lifetime is not None else None})
            minutes = [number(g.get("playtime_2weeks")) for g in recent]
            if all(m is not None for m in minutes):
                data["recent_hours"] = round(sum(minutes) / 60, 1)
            data["recent_status"] = "Available" if data["recent_hours"] is not None else "Playtime is hidden or unavailable."
        except (SteamError, KeyError, TypeError, AttributeError) as exc:
            data["recent_status"] = str(exc) if isinstance(exc, SteamError) else "Recent games unavailable."
        try:
            owned = game_list(client, sid)
            data["library_count"] = len(owned)
            data["playtime_status"] = "Available"
        except (SteamError, KeyError, TypeError, AttributeError) as exc:
            data["playtime_status"] = str(exc) if isinstance(exc, SteamError) else "Library unavailable."
        selected = game_id(config.get("game_id")) or data["current_game_id"] or (game_id(recent[0].get("appid")) if recent else None)
        data["game_id"] = selected
        if selected:
            found = next((g for g in owned + recent if game_id(g.get("appid")) == selected), {})
            data["game_name"] = clean(found.get("name")) or (data["current_game"] if selected == data["current_game_id"] else "") or f"GAME {selected}"
            lifetime = number(found.get("playtime_forever"))
            data["playtime_hours"] = round(lifetime / 60, 1) if lifetime is not None else None
            recent_minutes = next((number(g.get("playtime_2weeks")) for g in recent if game_id(g.get("appid")) == selected), None)
            data["game_recent_hours"] = round(recent_minutes / 60, 1) if recent_minutes is not None else None
            if lifetime is None:
                data["playtime_status"] = "Selected game's playtime is hidden or unavailable."
            try:
                stats = achievement_data(client, sid, selected)
                if not stats["game_name"]:
                    stats.pop("game_name")
                data.update(stats)
            except (SteamError, KeyError, TypeError, AttributeError) as exc:
                data["achievements_status"] = str(exc) if isinstance(exc, SteamError) else "Achievements unavailable."
        try:
            data["friends"] = friends_data(client, sid, favorite_ids(config.get("favorite_friends")), ttl)
            data.update(friends_available=True, friends_status="Available", friends_total=len(data["friends"]),
                        friends_online=sum(p["is_online"] for p in data["friends"]), friends_playing=sum(p["is_playing"] for p in data["friends"]))
        except (SteamError, KeyError, TypeError, AttributeError) as exc:
            data["friends_status"] = str(exc) if isinstance(exc, SteamError) else "Friends unavailable."
        return data


Plugin = SteamPlugin
