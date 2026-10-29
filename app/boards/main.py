"""Wires the layers together: one FastAPI app with the web routes, /mcp, and the sign-in
metadata Claude.ai and ChatGPT use to find where a person signs in (RFC 9728)."""
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route

from boards.application.use_cases import Boards
from boards.doors.identity import person_from
from boards.doors.mcp import build_mcp
from boards.doors.web import build_router
from boards.infrastructure.dodil import ModelsAssistant
from boards.infrastructure.repository import SqlBoards

APPID = os.environ.get("APPID_PUBLIC_URL", "https://appid.dodil.io").rstrip("/")
POOL = os.environ.get("DODIL_USER_POOL", "")  # "<org>/<pool>", set by .dodil/deploy.yaml
METADATA = "/.well-known/oauth-protected-resource"


def create_app(boards: Boards) -> FastAPI:
    gate = {"mcp": None}

    @asynccontextmanager
    async def lifespan(_app):
        mcp_app = build_mcp(boards).streamable_http_app(
            streamable_http_path="/mcp", stateless_http=True, json_response=True,
            # Every call carries identity only the gateway can mint, so host checks add nothing.
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
        gate["mcp"] = mcp_app
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(title="boards", lifespan=lifespan)

    def base(request: Request) -> str:
        h = request.headers
        return f"{h.get('x-forwarded-proto', 'https')}://{h.get('x-forwarded-host', h.get('host'))}"

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    @app.get(METADATA, include_in_schema=False)
    @app.get(METADATA + "/mcp", include_in_schema=False)
    def metadata(request: Request):
        return {"resource": base(request) + "/mcp", "authorization_servers": [f"{APPID}/{POOL}"],
                "bearer_methods_supported": ["header"], "resource_name": "boards"}

    class McpDoor:
        """No person → 401 with the metadata link, which is what starts Claude's sign-in.
        (A class, so Starlette hands it the raw ASGI call instead of a Request.)"""

        async def __call__(self, scope, receive, send):
            headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
            if person_from(headers) is None:
                body = json.dumps({"detail": "sign in first"}).encode()
                link = f'Bearer resource_metadata="{base(Request(scope))}{METADATA}/mcp"'
                await send({"type": "http.response.start", "status": 401, "headers": [
                    (b"content-type", b"application/json"), (b"www-authenticate", link.encode())]})
                await send({"type": "http.response.body", "body": body})
                return
            await gate["mcp"]({**scope, "path": "/mcp"}, receive, send)

    mcp_door = McpDoor()

    for path in ("/mcp", "/mcp/"):
        app.router.routes.append(Route(path, endpoint=mcp_door, methods=["GET", "POST", "DELETE"]))
    app.include_router(build_router(boards))
    return app


app = create_app(Boards(SqlBoards(), ModelsAssistant()))
