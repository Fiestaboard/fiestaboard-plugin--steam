# Steam setup and household pages

## 1. Create your personal API key

1. Sign in at [Steam's API-key page](https://steamcommunity.com/dev/apikey).
2. For a locally hosted FiestaBoard, enter **`localhost`** in **Domain Name**, without `https://`, a port or a path. This is also the local-hosting guidance in [EasyAdmin's Steam integration documentation](https://easyadmin.readthedocs.io/en/7.41/steamapikey/). Valve's general documentation describes associating a key with a domain but does not specify local-host validation rules.
3. Accept Steam's terms, register, and complete any Steam Guard confirmation requested by Steam.
4. Copy the key into FiestaBoard's **Steam Web API Key** field. You do not need to send the key to the plugin developer.

This is a Web API key, not an OAuth client ID. FiestaBoard makes outbound requests; no public domain, port forwarding, inbound Steam connection or callback URL is needed. If a key already exists, use the existing key rather than revoking credentials used by other applications.

## 2. Check Steam visibility

In Steam, open **Profile → Edit Profile → Privacy Settings**. For the complete dashboard, make the profile, relevant game details and friends list visible to the public API. The separate playtime-hiding option can still hide hours. Your husband's profile needs its own visibility settings checked too.

Friends-only visibility in the Steam client does not promise the same access through this API. Invisible/offline status, private games and hidden details can suppress activity. Family membership does not bypass those restrictions. Choose the visibility you are comfortable with; the plugin works with partial data and explains what is unavailable.

References: [Steam profile privacy](https://help.steampowered.com/en/faqs/view/588C-C67D-0251-C276), [private games](https://help.steampowered.com/en/faqs/view/1150-C06F-4D62-4966).

## 3. Configure one person

Open **Integrations**, find Steam and open its settings. Set:

- **Steam Web API Key:** your personal key.
- **Steam Profile:** a profile URL or 17-digit Steam ID. Both `https://steamcommunity.com/id/YOUR_NAME/` and `https://steamcommunity.com/profiles/YOUR_ID/` work. A login name by itself does not work.
- **Display Name:** optional friendly name for the board.
- **Display Mode:** Now Playing, Friends, or Achievement Chase.
- **Featured Game ID:** leave `0` for automatic selection. For a specific game, copy the number after `/app/` in its store URL. Portal 2, for example, is `620`.

Save and enable the integration. All variables are available regardless of display mode. The mode only controls the ready-made `line_1` through `line_6` card.

## 4. Add your husband or another person

Use Steam's **Add Instance** action to create instances labeled **`me`** and **`husband`**. Configure and enable each separately with the appropriate profile. The default `steam` instance can remain disabled when you only use named instances.

You can use the same personal key for publicly visible data from both people. Alternatively, set `STEAM_API_KEY` once in the server environment and leave each instance's key field blank. No shared key is bundled with this plugin.

Use stable instance labels: they form part of page variables. A display name can change without changing the instance namespace. A selected friend gets the same playtime and achievement fields as your own profile, subject to visibility.

## 5. Make pages

Create a page and select the person-specific Steam instance in the variable browser. For a six-row card that follows that instance's Display Mode:

```text
{{steam:me.line_1}}
{{steam:me.line_2}}
{{steam:me.line_3}}
{{steam:me.line_4}}
{{steam:me.line_5}}
{{steam:me.line_6}}
```

For a Note, use only `line_1` through `line_3`. These lines are rendered for the target board's actual size. For more than six rows, use the friends/recent-games variables to build additional rows; the plugin's complete formatted result also adapts to taller boards.

For your husband's own page, replace `steam:me` with `steam:husband`.

### Household page (Flagship, six rows)

```text
{{steam:me.player_name}}
{{steam:me.current_game}}
{{steam:me.status}}
{{steam:husband.player_name}}
{{steam:husband.current_game}}
{{steam:husband.status}}
```

Set name/game rows to wrap when desired, or use `|truncate:22` on a Flagship to keep each person within three rows. For a one-row idle fallback, the formula editor supports:

```text
{{= IF(steam:me.is_playing, steam:me.current_game, steam:me.status) }}
```

### Achievement page

Set the instance's Featured Game ID, then use:

```text
{{steam:husband.player_name}}
{{steam:husband.game_name}}
{{steam:husband.achievement_summary}}
{{steam:husband.latest_achievement}}
```

`achievement_summary` already explains unavailable data. For manual numeric layouts, check `achievements_available` before adding labels such as `%` or `TO GO`; unknown numbers render as `???`, not zero. Use `playtime_available` and `recent_available` to guard playtime fields.

### Friends and recent games

The variable browser exposes items in `friends` and `recent_games`. For example:

```text
{{steam:me.friends.0.name}}
{{steam:me.friends.0.game}}
{{steam:me.recent_games.0.name}}
{{steam:me.recent_games.0.recent_hours}}
```

Friends are ordered by playing, then online, then name. An index follows that ordering and is **not a permanent reference to one person**. For a page that must always show a specific person, create a named instance for their profile.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| API key required/rejected | Supply your personal key, remove surrounding whitespace, confirm any requested Steam Guard action. Environment fallback must exist inside the server/container. |
| Profile not found | Use the full Community profile URL or Steam ID, not a login name or store URL. |
| Friends unavailable | Check friends-list visibility. You can enter specific IDs under Favorite Friends instead. |
| `???` playtime | Check Game Details visibility and the playtime-hiding option. `???` means unavailable. |
| Achievements unavailable | The selected game may not expose achievements, may not have initialized stats for this player, or data may be private. Try a game the person has played. |
| Wrong game in achievement/playtime fields | Check Featured Game ID. These fields track the featured game; `current_game` always tracks visible current activity. |
| Husband's variables missing | Enable the `husband` instance after saving; look under its instance name in the variable browser. |
| Shared game missing from library count | This is the visible owned-games endpoint, not Steam Family entitlements. |
| Slow updates | Presence defaults to 60 seconds; stats cache for 5 minutes. Steam can add its own delay. |
| Rate limit/network error | Allow the retry cooldown to expire. Optional section failures do not erase the rest of the profile. |
| Long game titles | Use wrapping or truncation; the supplied mode-specific lines already adapt to board width. |

The setup walkthrough can be tested with synthetic profiles using the isolated UX harness in [TESTING.md](TESTING.md). It is separate from normal plugin operation.
