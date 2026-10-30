import importlib.util
import json
from unittest.mock import Mock

import pytest
import requests


@pytest.fixture
def api():
    assert importlib.util.find_spec("steam_api"), "Steam HTTP client has not been implemented"
    import steam_api
    return steam_api


def response(status=200, data=None):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(data if data is not None else {"response": {"ok": True}}).encode()
    return r


def test_header_auth_cache_and_expiry(api):
    get = Mock(return_value=response())
    now = [0.0]
    client = api.SteamClient("secret", transport=get, clock=lambda: now[0])
    assert client.get("ISteamUser", "GetPlayerSummaries", 2, {"steamids": "76561198000000001"}, 60)["response"]["ok"]
    client.get("ISteamUser", "GetPlayerSummaries", 2, {"steamids": "76561198000000001"}, 60)
    assert get.call_count == 1
    args, kwargs = get.call_args
    assert args == ("https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",)
    assert kwargs["headers"]["x-webapi-key"] == "secret"
    assert "key" not in kwargs["params"]
    assert kwargs["timeout"] == (3.05, 8)
    now[0] = 61
    client.get("ISteamUser", "GetPlayerSummaries", 2, {"steamids": "76561198000000001"}, 60)
    assert get.call_count == 2
    client.get("ISteamUser", "GetPlayerSummaries", 2, {"steamids": "76561198000000002"}, 60)
    assert get.call_count == 3


@pytest.mark.parametrize("profile", ["76561198000000001", "https://steamcommunity.com/profiles/76561198000000001/", "steamcommunity.com/profiles/76561198000000001"])
def test_numeric_profile_never_uses_network(api, profile):
    get = Mock(side_effect=AssertionError("Unexpected request"))
    assert api.SteamClient("key", transport=get).resolve_profile(profile) == "76561198000000001"


def test_vanity_url_resolves_on_fixed_steam_endpoint(api):
    get = Mock(return_value=response(data={"response": {"success": 1, "steamid": "76561198000000002"}}))
    client = api.SteamClient("key", transport=get)
    assert client.resolve_profile("https://steamcommunity.com/id/my-husband/") == "76561198000000002"
    assert get.call_args.kwargs["params"] == {"vanityurl": "my-husband"}


@pytest.mark.parametrize("profile", ["", "abc", "123", "https://evil.test/id/me", "https://steamcommunity.com.evil.test/id/me", "https://user@steamcommunity.com/id/me", "https://steamcommunity.com:444/id/me", "https://steamcommunity.com/id/me?x=1", "https://steamcommunity.com/id/../me", "18446744073709551616"])
def test_rejects_invalid_profiles(api, profile):
    with pytest.raises(api.SteamError, match="Steam"):
        api.SteamClient("key").resolve_profile(profile)


@pytest.mark.parametrize("status, message", [(401, "private"), (403, "API key"), (429, "rate limit"), (500, "unavailable")])
def test_safe_http_errors_and_failure_cooldown(api, status, message):
    get = Mock(return_value=response(status, {"error": "secret"}))
    client = api.SteamClient("secret", transport=get)
    for _ in range(2):
        with pytest.raises(api.SteamError, match=message) as e:
            client.get("ISteamUser", "GetFriendList", 1, {}, 900)
        assert "secret" not in str(e.value)
    assert get.call_count == 1


def test_network_exception_does_not_leak_key(api):
    client = api.SteamClient("secret", transport=Mock(side_effect=requests.Timeout("url?key=secret")))
    with pytest.raises(api.SteamError, match="reach Steam") as e:
        client.get("ISteamUser", "GetPlayerSummaries", 2, {}, 60)
    assert "secret" not in str(e.value)


@pytest.mark.parametrize("body", [b"<html>error</html>", b"[]", b"null"])
def test_invalid_json_payload(api, body):
    r = response()
    r._content = body
    client = api.SteamClient("key", transport=Mock(return_value=r))
    with pytest.raises(api.SteamError, match="invalid response"):
        client.get("ISteamUser", "GetPlayerSummaries", 2, {}, 60)


def test_missing_vanity_profile(api):
    client = api.SteamClient("key", transport=Mock(return_value=response(data={"response": {"success": 42}})))
    with pytest.raises(api.SteamError, match="not found"):
        client.resolve_profile("https://steamcommunity.com/id/missing")
