"""Text-only Steam cards that adapt to the bound board's geometry."""
import re
import textwrap


def clean(value):
    """Keep upstream names from creating board markup or additional rows."""
    return re.sub(r"\s+", " ", str(value or "").replace("{", "(").replace("}", ")")).strip()


def hours(value):
    return "?" if value is None else f"{value:g}"


def layout(data, mode, rows, cols):
    rows, cols = max(1, rows), max(1, cols)
    name = data["player_name"]
    if mode == "friends":
        if not data["friends_available"]:
            content = [name, "FRIENDS UNAVAILABLE"]
        else:
            content = [f'{data["friends_online"]} ONLINE / {data["friends_playing"]} PLAYING']
            active = [p for p in data["friends"] if p["is_online"]]
            for friend in active:
                content.extend([friend["name"], friend["game"] or friend["status"]])
            if not active:
                content += [name, "NO FRIENDS ONLINE"]
    elif mode == "achievements":
        if data["achievements_available"]:
            content = [name, data["game_name"], data["achievement_summary"], f'{data["achievements_remaining"]} TO GO']
            if data["latest_achievement"]:
                content += ["LATEST UNLOCK", data["latest_achievement"]]
        else:
            content = [name, data["game_name"] or "SELECT A GAME", "STATS UNAVAILABLE"]
    else:
        content = [name, "NOW PLAYING" if data["is_playing"] else data["status"].upper(), data["current_game"] or data["game_name"] or "NO RECENT GAME"]
        if not data["is_playing"] and data["game_name"]:
            content[1] = "RECENT GAME"
        # These statistics belong to the featured game; never label a different
        # current game with the manually selected game's playtime/achievements.
        if not data["current_game"] or data["current_game_id"] == data["game_id"]:
            if data["playtime_hours"] is not None:
                content += [f'{hours(data["playtime_hours"])} HOURS PLAYED']
            if data["achievements_available"]:
                content += [data["achievement_summary"]]
        if data["friends_available"]:
            content += [f'{data["friends_online"]} FRIENDS ONLINE']
        for game in data["recent_games"]:
            if game["appid"] != data["game_id"]:
                content += [game["name"], f'{hours(game["recent_hours"])} HOURS / 2 WEEKS']
    lines = []
    for item in content:
        lines.extend(textwrap.wrap(clean(item), cols, break_long_words=True, break_on_hyphens=False))
    # Narrow cards prioritize the person and game/progress rather than a
    # wrapped header consuming the entire screen.
    if rows <= 3:
        if mode == "achievements":
            lines = [name, data["game_name"] or "SELECT A GAME", data["achievement_summary"] if data["achievements_available"] else "STATS UNAVAILABLE"]
        elif mode == "now_playing":
            lines = [name, data["current_game"] or data["game_name"] or "NO RECENT GAME", "NOW PLAYING" if data["is_playing"] else data["status"].upper()]
        elif data["friends_available"]:
            active = [p for p in data["friends"] if p["is_online"]]
            lines = [f'{data["friends_online"]} ONLINE', active[0]["name"] if active else name, (active[0]["game"] or active[0]["status"]) if active else "NONE PLAYING"]
    fitted = []
    for line in lines[:rows]:
        line = clean(line)
        if len(line) > cols:
            line = line[:max(0, cols - 3)].rstrip() + ("..." if cols >= 3 else "." * cols)
        fitted.append(line.center(cols))
    return fitted + [" " * cols] * (rows - len(fitted))
