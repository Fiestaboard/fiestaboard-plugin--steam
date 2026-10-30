# Steam plugin design

## Agreed intent

Build a sibling FiestaBoard plugin for Steam. The user approved personal Web API keys and wants equal data for themselves, their husband, and any selected friend. Individual pages and a combined household page must work. Deliver setup documentation and actual UX verification.

## Approach

Use the existing Python PluginBase API and named instances (`steam:me`, `steam:husband`). Each instance selects one Steam ID or profile URL and exposes the same fields. Each may use its own key or a locally configured STEAM_API_KEY. There is no bundled credential, OAuth client, or hosted proxy. Public-only game news/player counts were considered but do not meet the personal-data requirement. Steam OAuth is not available for this dashboard use case.

## Version-one scope

- Now Playing, Friends, and Achievement Chase display modes.
- Profile name, visible status/current game, recent games and playtime, selected-game playtime, achievement count/total/percentage/remaining and latest achievement.
- Friends summary and array, optional favorite Steam IDs, playing friends first. Batch summaries in groups of at most 100.
- A selected game ID overrides the current game; otherwise the current game or a recent game is featured; Steam does not document recent-game ordering.
- Scalar variables and arrays usable across named instances on one page; a ready-made formatted display and device demo templates.
- Support every board geometry via board.rows/cols, including Flagship, Note, and Note Array.

## Data and safety

Use HTTPS api.steampowered.com only, a request header for the key, bounded timeouts, no secrets in error messages/logs. Accept numeric 64-bit IDs or steamcommunity.com profile/vanity URLs; never request a user-provided URL. Preserve Steam IDs as strings. Public API visibility is authoritative: family membership is not authorization. Missing data is unavailable, never fabricated zero. Per-game stats stay per person, including borrowed games where Steam exposes them. Friends and stats failures do not discard a successful profile result. Counts must not masquerade as complete if friend summary batches fail.

Cache raw endpoint data per instance: presence 60s (configurable >=30), stats 5m, friend list 15m, schemas 24h, vanity resolution 24h. Cache keys include resource parameters; clear on configuration changes. Failures are briefly cached to avoid retry storms. Do not silently present stale activity as live. No historical tracking, notifications, household auto-discovery, family-library entitlement claims, rich presence or exact session timers in v1.

## Verification

Use deterministic Steam HTTP fixtures for privacy, failures and two independent profiles; no real credentials are available. Run tests against real FiestaBoard classes and template engine. Run browser checks in an isolated FiestaBoard instance with synthetic Steam HTTP responses, preserving the real plugin, backend and frontend. Test setup, separate instances, variable discovery, shared page rendering, narrow layouts and errors. Report authenticated live verification separately if credentials are not supplied.

## References

- https://partner.steamgames.com/doc/webapi/ISteamUser
- https://partner.steamgames.com/doc/webapi/IPlayerService
- https://partner.steamgames.com/doc/webapi/ISteamUserStats
- https://partner.steamgames.com/doc/webapi_overview/auth
- https://partner.steamgames.com/doc/webapi_overview/oauth
- https://help.steampowered.com/en/faqs/view/054C-3167-DD7F-49D4
