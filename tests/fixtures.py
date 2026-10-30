"""Synthetic people and Steam responses. These IDs are test data, not live accounts."""
import json
import requests

ME = "76561198000000001"
HUSBAND = "76561198000000002"
FRIEND = "76561198000000003"


def steam_response(status, data):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    return result


class SteamTransport:
    def __init__(self):
        self.calls = []
        self.overrides = {}
        self.players = {
            ME: {"steamid": ME, "personaname": "Jeff", "personastate": 1, "communityvisibilitystate": 3, "gameid": "620", "gameextrainfo": "Portal 2"},
            HUSBAND: {"steamid": HUSBAND, "personaname": "Husband", "personastate": 3, "communityvisibilitystate": 3, "gameid": "1145360", "gameextrainfo": "Hades"},
            FRIEND: {"steamid": FRIEND, "personaname": "Alex", "personastate": 1, "communityvisibilitystate": 3},
        }

    def __call__(self, url, *, params, **kwargs):
        method = url.split("/")[-3]
        self.calls.append((method, dict(params), kwargs))
        if method in self.overrides:
            override = self.overrides[method]
            if callable(override):
                return override(params)
            return steam_response(*override)
        sid = params.get("steamid", ME)
        if method == "ResolveVanityURL":
            data = {"response": {"success": 1, "steamid": HUSBAND if params["vanityurl"] == "husband" else ME}}
        elif method == "GetPlayerSummaries":
            data = {"response": {"players": [self.players[x] for x in params["steamids"].split(",") if x in self.players]}}
        elif method == "GetFriendList":
            data = {"friendslist": {"friends": [{"steamid": x, "relationship": "friend", "friend_since": 1600000000} for x in (HUSBAND, FRIEND) if x != sid]}}
        elif method in ("GetRecentlyPlayedGames", "GetOwnedGames"):
            games = [{"appid": 620, "name": "Portal 2", "playtime_forever": 600 if sid == ME else 1800, "playtime_2weeks": 120}, {"appid": 1145360, "name": "Hades", "playtime_forever": 1200, "playtime_2weeks": 60}]
            data = {"response": {"games": games, "total_count" if method == "GetRecentlyPlayedGames" else "game_count": 2}}
        elif method == "GetPlayerAchievements":
            data = {"playerstats": {"steamID": sid, "gameName": "Portal 2" if int(params["appid"]) == 620 else "Hades", "success": True, "achievements": [{"apiname": "A", "achieved": 1, "unlocktime": 1700000000}, {"apiname": "B", "achieved": 1 if sid == ME else 0, "unlocktime": 1700000100 if sid == ME else 0}, {"apiname": "C", "achieved": 0, "unlocktime": 0}]}}
        elif method == "GetSchemaForGame":
            data = {"game": {"gameName": "Portal 2" if int(params["appid"]) == 620 else "Hades", "availableGameStats": {"achievements": [{"name": "A", "displayName": "Wake Up Call"}, {"name": "B", "displayName": "You Monster"}, {"name": "C", "displayName": "Hidden", "hidden": 1}]}}}
        else:
            raise AssertionError(f"Unexpected Steam method {method}")
        return steam_response(200, data)
