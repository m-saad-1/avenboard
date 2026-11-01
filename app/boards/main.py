"""Same-origin FastAPI application, official MCP transport and gateway OAuth discovery."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route
from boards.application.use_cases import Boards
from boards.doors.identity import person_from
from boards.doors.mcp import build_mcp
from boards.doors.web import build_router
from boards.domain.model import AppError
from boards.infrastructure.dodil import ModelsAssistant
from boards.infrastructure.repository import SqlBoards
from boards.infrastructure.logging import configure

METADATA = "/.well-known/oauth-protected-resource"
logger = logging.getLogger("avenboard")


def create_app(boards, identify=person_from):
    configure()
    gate = {"mcp": None}

    async def index_worker():
        while True:
            try:
                await asyncio.to_thread(boards.process_embeddings, limit=5)
            except Exception:
                logger.warning("embedding_batch_failed")
            await asyncio.sleep(30)

    @asynccontextmanager
    async def lifespan(app):
        if os.environ.get("DEV_USER"):
            raise RuntimeError(
                "DEV_USER is prohibited. Use genuine appid identity; tests inject a resolver."
            )
        mcp_app = build_mcp(boards, identify).streamable_http_app(
            streamable_http_path="/mcp",
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            ),
        )
        gate["mcp"] = mcp_app
        worker = None
        async with mcp_app.router.lifespan_context(mcp_app):
            if getattr(boards.assistant, "semantic_enabled", False):
                worker = asyncio.create_task(index_worker())
            try:
                yield
            finally:
                if worker:
                    worker.cancel()
                    with suppress(asyncio.CancelledError):
                        await worker

    app = FastAPI(
        title="Avenboard",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.boards = boards

    def base(request):
        configured = os.environ.get("APP_PUBLIC_URL")
        if configured:
            return configured.rstrip("/")
        h = request.headers
        return f"{h.get('x-forwarded-proto', 'https')}://{h.get('x-forwarded-host', h.get('host', 'localhost'))}"

    @app.middleware("http")
    async def protect(request, call_next):
        started = time.monotonic()
        if request.url.path.startswith("/api") and request.method not in (
            "GET",
            "HEAD",
            "OPTIONS",
        ):
            if request.headers.get("x-avenboard-request") != "1":
                return JSONResponse(
                    {"code": "csrf", "message": "Missing same-origin request header"},
                    status_code=403,
                )
            origin = request.headers.get("origin")
            expected = base(request)
            local = f"{request.url.scheme}://{request.headers.get('host')}"
            if origin and origin not in (expected, local):
                return JSONResponse(
                    {"code": "csrf", "message": "Cross-origin writes are not allowed"},
                    status_code=403,
                )
        response = await call_next(request)
        logger.info(
            "request_complete",
            extra={
                "metrics": {
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "transport"),
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            },
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith(("/api", "/mcp")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def domain_error(request, exc):
        return JSONResponse(
            {"code": exc.code, "message": str(exc)}, status_code=exc.status
        )

    @app.get("/healthz", include_in_schema=False)
    def health():
        return {"ok": True, "service": "avenboard"}

    @app.post("/", include_in_schema=False)
    def self_check(request: Request):
        # A deployment probe is intentionally distinct from end-user operations.
        if request.headers.get("x-dodil-auth-source") != "platform":
            return JSONResponse(
                {"code": "forbidden", "message": "Platform probe only"}, status_code=403
            )
        return boards.repo.diagnostics()

    @app.get(METADATA, include_in_schema=False)
    @app.get(METADATA + "/mcp", include_in_schema=False)
    def metadata(request: Request):
        issuer = os.environ.get("APPID_PUBLIC_URL", "https://appid.dodil.io").rstrip(
            "/"
        )
        return {
            "resource": base(request) + "/mcp",
            "authorization_servers": [
                issuer + "/" + os.environ.get("DODIL_USER_POOL", "")
            ],
            "bearer_methods_supported": ["header"],
            "resource_name": "Avenboard",
        }

    class McpDoor:
        async def __call__(self, scope, receive, send):
            headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
            if identify(headers) is None:
                link = (
                    f'Bearer resource_metadata="{base(Request(scope))}{METADATA}/mcp"'
                )
                response = JSONResponse(
                    {
                        "code": "unauthenticated",
                        "message": "Sign in through Dodil appid",
                    },
                    status_code=401,
                    headers={"WWW-Authenticate": link},
                )
                await response(scope, receive, send)
                return
            await gate["mcp"]({**scope, "path": "/mcp"}, receive, send)

    door = McpDoor()
    for path in ("/mcp", "/mcp/"):
        app.router.routes.append(
            Route(path, endpoint=door, methods=["GET", "POST", "DELETE"])
        )
    app.include_router(build_router(boards, identify))

    static = Path(__file__).parent / "static"
    if (static / "assets").exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str, request: Request):
        if path.startswith(("api/", "mcp/")):
            return JSONResponse(
                {"code": "not_found", "message": "Route not found"}, status_code=404
            )
        if not identify(request.headers):
            return RedirectResponse("/.dodil/auth/login?return_to=%2F", status_code=303)
        if not (static / "index.html").exists():
            return JSONResponse(
                {
                    "code": "build_required",
                    "message": "Build the frontend before starting the app.",
                },
                status_code=503,
            )
        return FileResponse(static / "index.html")

    return app


app = create_app(Boards(SqlBoards(), ModelsAssistant()))
