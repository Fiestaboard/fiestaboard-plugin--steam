"""Small, credential-safe boundary around the public Steam Web API."""
from copy import deepcopy
import json
import re
import threading
import time
from urllib.parse import urlsplit

import requests


class SteamError(Exception):
    """An actionable message safe to display or log (never a request URL)."""


def parse_profile(value):
    """Return (kind, value), accepting IDs or Steam Community profile URLs only."""
    value = str(value or "").strip()
    if re.fullmatch(r"\d{17}", value) and 0 < int(value) < 2**64:
        return "id", value
    if value.startswith("steamcommunity.com/"):
        value = "https://" + value
    parsed = urlsplit(value)
    if (parsed.scheme in ("https", "http") and parsed.netloc.lower() == "steamcommunity.com"
            and not parsed.query and not parsed.fragment):
        match = re.fullmatch(r"/profiles/(\d{17})/?", parsed.path)
        if match:
            return "id", match[1]
        match = re.fullmatch(r"/id/([A-Za-z0-9_-]{1,100})/?", parsed.path)
        if match:
            return "vanity", match[1]
    raise SteamError("Enter a 17-digit Steam ID or a steamcommunity.com/id/ or /profiles/ URL.")


class SteamClient:
    """Per-instance cache; no network call ever follows a supplied profile URL."""

    def __init__(self, api_key, transport=None, clock=None):
        self._key = api_key
        self._transport = transport or requests.get
        self._clock = clock or time.monotonic
        self._cache = {}
        self._lock = threading.RLock()

    def get(self, interface, method, version, params, ttl):
        identity = (interface, method, version, json.dumps(params, sort_keys=True))
        with self._lock:
            now = self._clock()
            entry = self._cache.get(identity)
            if entry and entry[0] > now:
                if isinstance(entry[1], SteamError):
                    raise SteamError(str(entry[1]))
                return deepcopy(entry[1])
            try:
                response = self._transport(
                    f"https://api.steampowered.com/{interface}/{method}/v{version}/",
                    params=params, headers={"x-webapi-key": self._key}, timeout=(3.05, 8),
                    allow_redirects=False,
                )
                errors = {
                    401: "Steam data is private or access is not authorized.",
                    403: "Steam rejected the API key. Check or replace it in settings.",
                    429: "Steam rate limit reached. Please try again later.",
                }
                if response.status_code != 200:
                    raise SteamError(errors.get(response.status_code, "Steam is temporarily unavailable. Please try again later."))
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("not an object")
            except ValueError:
                error = SteamError("Steam returned an invalid response. Please try again later.")
            except requests.RequestException:
                error = SteamError("Could not reach Steam. Check your connection and try again.")
            except SteamError as exc:
                error = exc
            else:
                # Expire old entries and cap growth when a profile plays many games.
                self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
                if len(self._cache) >= 256:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[identity] = (self._clock() + ttl, deepcopy(data))
                return data
            self._cache[identity] = (self._clock() + 30, error)
            raise error from None

    def resolve_profile(self, profile):
        kind, value = parse_profile(profile)
        if kind == "id":
            return value
        data = self.get("ISteamUser", "ResolveVanityURL", 1, {"vanityurl": value}, 86400).get("response")
        if isinstance(data, dict) and data.get("success") == 1:
            try:
                kind, steam_id = parse_profile(data.get("steamid"))
                if kind == "id":
                    return steam_id
            except SteamError:
                pass
        raise SteamError("Steam profile not found. Check the profile URL.")
