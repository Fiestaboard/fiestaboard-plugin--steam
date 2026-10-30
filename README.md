# Steam for FiestaBoard

Show what you or your friends are playing, how much you have played, and how close you are to finishing a game's achievements. Configure a separate instance for each person, then use their variables on individual pages or together on a household page.

**[Setup and household pages](docs/SETUP.md)** · **[Testing and UX verification](docs/TESTING.md)**

## Features

- **Now Playing:** selected person's visible activity, with a recent-game fallback while idle.
- **Friends:** online/in-game counts and a list sorted with playing friends first. Optionally follow specific Steam IDs instead of the complete friends list.
- **Achievement Chase:** unlocked/total, percentage, remaining, and latest unlock for a featured game.
- **Playtime:** featured-game lifetime hours, recent two-week hours, and recent games.
- **Multiple people:** `steam:me` and `steam:husband` expose the same fields. No profile is restricted to a subset of features.
- **Multiple boards:** board-aware layouts for Flagship, Note, Note Array and other text grids, including narrow LED grids.

Requires FiestaBoard **10.0.0 or later**, Python 3.12+, a personal Steam Web API key and visible Steam data. Uses `requests`, already supplied by FiestaBoard. No subscription, developer credential, OAuth application or public callback server is required.

## Installation

This repository is a standalone data plugin with manifest ID `steam`.

For local development, copy or mount this directory as `plugins/steam` inside a FiestaBoard checkout/container and restart FiestaBoard. Example bind mount, added to your existing service:

```yaml
volumes:
  - /absolute/path/to/fiestaboard-plugin--steam:/app/plugins/steam:ro
```

Mount the **whole directory**, including `steam_api.py` and `display.py`. For a Git-based installation after you publish this repository, use FiestaBoard's custom Git plugin installer with the actual repository URL. This local deliverable has not been published or added to the public registry.

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `profile` | Required | 17-digit Steam ID, `/profiles/ID` URL, or `/id/NAME` URL |
| `api_key` | Server environment fallback | Your personal Web API key; masked in the settings form |
| `display_name` | Steam persona name | Friendly label on the board |
| `display_mode` | `now_playing` | `now_playing`, `friends`, or `achievements` |
| `game_id` | `0` | Featured app ID; 0 selects current game, then a recent game |
| `favorite_friends` | Empty | Comma-separated Steam IDs; empty uses visible friends list |
| `refresh_seconds` | `60` | Presence refresh, 30–3600 seconds |

`STEAM_API_KEY` may be set in the FiestaBoard server environment. Instances with an empty API Key setting use it. An instance's nonempty key takes precedence. Environment variables must be present inside the container, not just in your host shell. Changes to environment configuration normally require recreating/restarting the container.

**The key is still a credential.** Keep it on your own installation, out of Git and shared screenshots. The plugin sends it in an HTTPS request header, never in a query URL or template variable. Password masking is a UI feature, not a guarantee that host configuration files are encrypted.

## Data semantics

Every display mode exposes all variables. `current_game` always describes visible current activity. `game_name`, playtime and achievements describe the **featured** game. If you manually select a different featured game, the Now Playing card does not attach its statistics to the current game's title.

Unavailable numeric fields are `null` (displayed as `???` by FiestaBoard in ordinary numeric variables), not zero. Use availability booleans/status fields or a formula to show a fallback. `recent_hours` is the sum of reported `playtime_2weeks` values, converted from minutes and rounded once to one decimal. It is a rolling two-week window, not a calendar week or time played today. Lifetime hours are also rounded to one decimal.

`friends_online` includes friends in games. Counts cover **Favorites** when configured, otherwise **All friends**. A failed or omitted friend-summary batch makes the counts unavailable; the plugin does not present partial counts as complete. Favorites can be followed by ID even when the selected person's friend list is private; each favorite's own visibility still applies.

Achievement counts apply to one game and one person. They are not a library-wide achievement total. A visible empty achievement list yields zero unlocked/total and an unavailable completion percentage. Unsupported/private achievement data stays unavailable. Unlocks with zero or missing timestamps still count, but cannot establish which achievement was latest. If no unlocked achievement has a positive timestamp, the latest achievement name stays empty and its timestamp is unavailable.

Steam Families does not grant this plugin additional access. Shared-game achievements belong to the player who earned them. `library_count` is the API's visible owned-game count, **not** an entitlement count for the combined Steam Family library. Borrowed-game data is displayed only where the API exposes it.

## Refresh and reliability

| Data | Cache lifetime |
| --- | --- |
| Profile and friend presence | Configured activity refresh, default 60 seconds |
| Library, recent playtime, player achievements | 5 minutes |
| Friends list membership | 15 minutes |
| Achievement names/schema and vanity resolution | 24 hours |
| Request failures | 30 seconds |

The plugin bypasses the host’s whole-result cache and caches HTTP responses itself, so changing board geometry cannot extend the life of old activity. Caches are in memory and independent per instance; configuration changes clear them. Steam itself may report playtime or achievements with additional delay. There are no push notifications or guaranteed real-time updates.

Profile requests batch at most 100 Steam IDs. Calls use bounded connect/read timeouts. Optional data failures leave successful profile fields available and explain the failed section. Failed profile fetches return a plugin error. Expired activity is not silently returned as current.

## APIs

All requests use `https://api.steampowered.com`.

| Interface | Methods |
| --- | --- |
| `ISteamUser` | `ResolveVanityURL/v1`, `GetPlayerSummaries/v2`, `GetFriendList/v1` |
| `IPlayerService` | `GetRecentlyPlayedGames/v1`, `GetOwnedGames/v1` |
| `ISteamUserStats` | `GetPlayerAchievements/v1`, `GetSchemaForGame/v2` |

Official references: [profiles/friends](https://partner.steamgames.com/doc/webapi/ISteamUser), [playtime/library](https://partner.steamgames.com/doc/webapi/IPlayerService), [achievements](https://partner.steamgames.com/doc/webapi/ISteamUserStats), [API-key authentication](https://partner.steamgames.com/doc/webapi_overview/auth), [OAuth restrictions](https://partner.steamgames.com/doc/webapi_overview/oauth), [Steam Families](https://help.steampowered.com/en/faqs/view/054C-3167-DD7F-49D4).

Not included in v1: automatic household discovery, exact session duration, historical daily tracking, achievement notifications, library-wide achievement scanning, rich in-game status, backlog recommendations, prices, news or global player counts.

## Development

See [testing instructions](docs/TESTING.md). Tests use real FiestaBoard classes and synthetic Steam HTTP responses; no credentials are needed. The plugin never imports the UX fixture server in production.

## Template variables

The base instance uses `{{steam.FIELD}}`. Named instances use `{{steam:me.FIELD}}` and `{{steam:husband.FIELD}}`. The complete field reference follows.

| Field | Type | Meaning |
| --- | --- | --- |
| `player_name` | string | Selected player name |
| `steam_id` | string | Selected player Steam ID |
| `profile_url` | string | Steam Community profile URL |
| `status` | string | Visible Steam status |
| `is_playing` | boolean | Whether Steam exposes an in-game activity |
| `current_game` | string | Game currently playing, unavailable if not visible |
| `current_game_id` | number | Current Steam app ID, unavailable if unavailable |
| `game_id` | number | Selected, current, or a recent game ID |
| `game_name` | string | Featured game title |
| `playtime_hours` | number | Featured game lifetime hours; unavailable if hidden |
| `game_recent_hours` | number | Featured game hours in the last two weeks; unavailable if unavailable |
| `recent_hours` | number | Hours across recently played games in the last two weeks |
| `library_count` | number | Visible owned-game count, not family library size |
| `playtime_status` | string | Availability of featured-game playtime |
| `recent_status` | string | Availability of recent games and playtime |
| `friends_online` | number | Online friends including those playing; unavailable if unavailable |
| `friends_playing` | number | Friends currently in game; unavailable if unavailable |
| `friends_total` | number | Number of friends in selected scope |
| `friends_available` | boolean | Whether friend counts are complete |
| `friends_status` | string | Friends data availability or explanation |
| `friends_scope` | string | All friends or Favorites |
| `achievements_unlocked` | number | Featured game unlocked achievement count |
| `achievements_total` | number | Featured game achievement count |
| `achievements_remaining` | number | Achievements still locked |
| `achievement_percent` | number | Completion percentage; unavailable if unknown or no achievements |
| `achievement_summary` | string | Ready-to-display achievement count or status |
| `achievements_available` | boolean | Whether achievement counts are available |
| `achievements_status` | string | Achievement data availability or explanation |
| `latest_achievement` | string | Latest unlocked achievement in the featured game |
| `latest_unlock_time` | number | Latest known unlock Unix timestamp; unavailable if no positive unlock time exists |
| `line_1` | string | Row 1 of the selected display mode, adapted to the current board |
| `line_2` | string | Row 2 of the selected display mode, adapted to the current board |
| `line_3` | string | Row 3 of the selected display mode, adapted to the current board |
| `line_4` | string | Row 4 of the selected display mode, adapted to the current board |
| `line_5` | string | Row 5 of the selected display mode, adapted to the current board |
| `line_6` | string | Row 6 of the selected display mode, adapted to the current board |
| `playtime_available` | boolean | Whether featured-game lifetime hours are visible; use for a template fallback |
| `recent_available` | boolean | Whether total two-week hours are visible; use for a template fallback |

Arrays: `friends` exposes `steam_id`, `name`, `status`, `game`, `is_online`, `is_playing`. `recent_games` exposes `appid`, `name`, `recent_hours`, `playtime_hours`. Indices are zero-based and follow changing source order.
