import json
from pathlib import Path

import pytest

from conftest import ROOT, load_plugin
from fixtures import ME, HUSBAND, FRIEND, SteamTransport, steam_response


@pytest.fixture
def module():
    assert (ROOT / "__init__.py").exists(), "Steam plugin is not implemented"
    return load_plugin()


@pytest.fixture
def transport(module, monkeypatch):
    transport = SteamTransport()
    monkeypatch.setattr(module.steam_api.requests, "get", transport)
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    return transport


def plugin(module, **config):
    p = module.Plugin(json.loads((ROOT / "manifest.json").read_text()))
    p.config = {"api_key": "test-key", "profile": ME, **config}
    return p


def test_two_profiles_have_equal_independent_data(module, transport):
    a = plugin(module).fetch_data()
    b = plugin(module, profile=HUSBAND).fetch_data()
    assert a.available and b.available
    assert a.data["player_name"] == "Jeff"
    assert b.data["player_name"] == "Husband"
    assert a.data["game_name"] == "Portal 2"
    assert b.data["game_name"] == "Hades"
    assert a.data["achievements_unlocked"] == 2
    assert b.data["achievements_unlocked"] == 1
    assert a.data["achievement_percent"] == 67
    assert b.data["achievement_percent"] == 33
    assert a.data["playtime_hours"] == 10
    assert b.data["playtime_hours"] == 20
    assert a.data["recent_hours"] == 3
    assert a.data["latest_achievement"] == "You Monster"


def test_selected_game_overrides_current_but_preserves_now_playing(module, transport):
    data = plugin(module, game_id=1145360).fetch_data().data
    assert data["current_game"] == "Portal 2"
    assert data["game_name"] == "Hades"
    assert data["playtime_hours"] == 20


def test_idle_uses_recent_game(module, transport):
    transport.players[ME].pop("gameid")
    transport.players[ME].pop("gameextrainfo")
    data = plugin(module).fetch_data().data
    assert data["is_playing"] is False
    assert data["current_game"] == ""
    assert data["game_name"] == "Portal 2"
    assert data["status"] == "Online"


def test_friends_counts_sort_and_favorite_scope(module, transport):
    data = plugin(module, display_mode="friends").fetch_data().data
    assert data["friends_online"] == 2
    assert data["friends_playing"] == 1
    assert [p["name"] for p in data["friends"]] == ["Husband", "Alex"]
    scoped = plugin(module, favorite_friends=FRIEND).fetch_data().data
    assert scoped["friends_online"] == 1
    assert scoped["friends_playing"] == 0
    assert scoped["friends_scope"] == "Favorites"


def test_private_friends_does_not_hide_profile_or_fabricate_counts(module, transport):
    transport.overrides["GetFriendList"] = (401, {})
    result = plugin(module, display_mode="friends").fetch_data()
    assert result.available
    assert result.data["player_name"] == "Jeff"
    assert result.data["friends_online"] is None
    assert "private" in result.data["friends_status"]
    assert "UNAVAILABLE" in " ".join(result.formatted_lines)


def test_favorites_work_without_public_friend_list(module, transport):
    transport.overrides["GetFriendList"] = (401, {})
    result = plugin(module, favorite_friends=HUSBAND).fetch_data()
    assert result.data["friends_online"] == 1
    assert not any(c[0] == "GetFriendList" for c in transport.calls)


def test_private_stats_and_missing_playtime_are_unknown(module, transport):
    transport.overrides["GetPlayerAchievements"] = (200, {"playerstats": {"success": False, "error": "secret error"}})
    transport.overrides["GetOwnedGames"] = (200, {"response": {}})
    transport.overrides["GetRecentlyPlayedGames"] = (200, {"response": {}})
    data = plugin(module).fetch_data().data
    assert data["achievements_unlocked"] is None
    assert data["achievement_percent"] is None
    assert data["playtime_hours"] is None
    assert data["recent_hours"] is None
    assert "secret" not in str(data)


def test_visible_empty_library_and_no_achievements(module, transport):
    transport.players[ME].pop("gameid")
    transport.players[ME].pop("gameextrainfo")
    transport.overrides["GetRecentlyPlayedGames"] = (200, {"response": {"total_count": 0}})
    transport.overrides["GetOwnedGames"] = (200, {"response": {"game_count": 0}})
    data = plugin(module).fetch_data().data
    assert data["library_count"] == 0
    assert data["recent_hours"] == 0
    assert data["achievement_percent"] is None
    assert data["game_name"] == ""


def test_hidden_playtime_is_not_zero(module, transport):
    transport.overrides["GetOwnedGames"] = (200, {"response": {"game_count": 1, "games": [{"appid": 620, "name": "Portal 2"}]}})
    transport.overrides["GetRecentlyPlayedGames"] = (200, {"response": {"total_count": 1, "games": [{"appid": 620, "name": "Portal 2"}]}})
    data = plugin(module).fetch_data().data
    assert data["playtime_hours"] is None
    assert data["recent_hours"] is None


def test_many_friends_batch_at_100_and_partial_data_is_unknown(module, transport):
    ids = [str(76561198000001000 + n) for n in range(205)]
    for sid in ids:
        transport.players[sid] = {"steamid": sid, "personaname": sid, "personastate": 1}
    p = plugin(module, favorite_friends=",".join(ids))
    data = p.fetch_data().data
    assert data["friends_online"] == 205
    calls = [x[1]["steamids"].split(",") for x in transport.calls if x[0] == "GetPlayerSummaries"]
    assert [len(x) for x in calls] == [1, 100, 100, 5]
    transport.players.pop(ids[-1])
    partial = plugin(module, favorite_friends=",".join(ids)).fetch_data().data
    assert partial["friends_online"] is None
    assert partial["friends_available"] is False


@pytest.mark.parametrize("method,payload", [("GetFriendList", {"friendslist": None}), ("GetRecentlyPlayedGames", {"response": None}), ("GetOwnedGames", {"response": {"games": [None]}}), ("GetPlayerAchievements", {"playerstats": {"success": True, "achievements": [None]}})])
def test_malformed_optional_payload_does_not_crash_profile(module, transport, method, payload):
    transport.overrides[method] = (200, payload)
    result = plugin(module).fetch_data()
    assert result.available
    assert result.data["player_name"] == "Jeff"


def test_missing_profile_and_invalid_key_are_actionable(module, transport):
    transport.overrides["GetPlayerSummaries"] = (403, {})
    result = plugin(module).fetch_data()
    assert result.available is False
    assert "API key" in result.error
    assert "test-key" not in result.error


def test_config_change_clears_user_and_game_caches(module, transport):
    p = plugin(module)
    assert p.fetch_data().data["player_name"] == "Jeff"
    p.config = {**p.config, "profile": HUSBAND}
    assert p.fetch_data().data["player_name"] == "Husband"


def test_cache_reused_across_board_shapes(module, transport):
    from src.devices import BoardContext
    p = plugin(module)
    a = p.get_data(BoardContext("flagship", rows=6, cols=22))
    count = len(transport.calls)
    b = p.get_data(BoardContext("note", rows=3, cols=15))
    assert len(transport.calls) == count
    assert len(a.formatted_lines) == 6
    assert len(b.formatted_lines) == 3
    assert all(len(x) == 15 for x in b.formatted_lines)


@pytest.mark.parametrize("mode", ["now_playing", "friends", "achievements"])
def test_geometry_and_no_markup_injection(module, transport, mode):
    from src.devices import BoardContext
    transport.players[ME]["personaname"] = "{{red}} JEFF\n{66}"
    p = plugin(module, display_mode=mode)
    for rows, cols in [(6, 22), (3, 15), (3, 30), (12, 15), (8, 10), (24, 120)]:
        result = p.get_data(BoardContext("panel", rows=rows, cols=cols))
        assert len(result.formatted_lines) == rows
        assert all(len(x) == cols for x in result.formatted_lines)
        assert "{" not in "".join(result.formatted_lines)


def test_validation_and_environment_key(module, transport, monkeypatch):
    p = plugin(module)
    assert p.validate_config({"profile": ME, "api_key": "key"}) == []
    assert p.validate_config({"profile": ME})
    monkeypatch.setenv("STEAM_API_KEY", "local-key")
    assert p.validate_config({"profile": ME}) == []
    assert p.validate_config({"profile": ME, "refresh_seconds": 1})
    assert p.validate_config({"profile": ME, "display_mode": "bad"})
    assert p.validate_config({"profile": ME, "favorite_friends": "not-an-id"})
    assert p.validate_config({"profile": ME, "game_id": -1})


def test_manifest_and_household_template(module, transport):
    from src.plugins.manifest import validate_manifest
    from src.templates.engine import TemplateEngine
    manifest = json.loads((ROOT / "manifest.json").read_text())
    valid, errors = validate_manifest(manifest)
    assert valid, errors
    a, b = plugin(module).fetch_data().data, plugin(module, profile=HUSBAND).fetch_data().data
    assert set(manifest["variables"]["simple"]) <= set(a)
    result = TemplateEngine().render("{{steam:me.current_game}}\n{{steam:husband.current_game}}", {"steam:me": a, "steam:husband": b})
    assert "Portal 2" in str(result) and "Hades" in str(result)
