"""Run ONLY in a disposable container: real FiestaBoard with fake Steam HTTP.

This is deliberately not imported by the production plugin. It binds to the
container; publish its port on 127.0.0.1 only. Never pass real Steam credentials.
"""
import sys
from pathlib import Path

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/plugins/steam/tests")

import requests
from fixtures import SteamTransport, steam_response

transport = SteamTransport()
real_get = requests.get


def fixture_get(url, **kwargs):
    if url.startswith("https://api.steampowered.com/"):
        key = kwargs.get("headers", {}).get("x-webapi-key")
        if key == "invalid-test-key":
            return steam_response(403, {})
        if key == "private-test-key" and "/GetFriendList/" in url:
            return steam_response(401, {})
        return transport(url, **kwargs)
    return real_get(url, **kwargs)


requests.get = fixture_get

from src.api_server import app as core_app
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

web = Path("/app/web/build/client")


@asynccontextmanager
async def lifespan(app):
    async with core_app.router.lifespan_context(core_app):
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/api", core_app)
app.mount("/assets", StaticFiles(directory=web / "assets"), name="ux-assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    target = (web / path).resolve()
    if target.is_relative_to(web) and target.is_file():
        return FileResponse(target)
    return FileResponse(web / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
