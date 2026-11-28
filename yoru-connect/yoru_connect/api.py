"""HTTPS API for enrolled Yoru Connect accounts."""

import time
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Settings, tunnel_addresses, wireguard_key
from .storage import AccessRequired, Capacity, Conflict, Denied, Store, token_digest


class Enrollment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_key: str = Field(min_length=44, max_length=44)

    @field_validator("public_key")
    @classmethod
    def check_public_key(cls, value: str) -> str:
        return wireguard_key(value)


def require_token(authorization: str = Header(default="")) -> bytes:
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer":
        raise Denied("A Bearer access token is required")
    return token_digest(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.database)
    store.initialize()
    app = FastAPI(title="Yoru Connect", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def prevent_response_caching(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Denied)
    async def bad_token(request: Request, exc: Denied) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=401, headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(AccessRequired)
    async def plan_required(request: Request, exc: AccessRequired) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(Conflict)
    @app.exception_handler(Capacity)
    async def enrollment_conflict(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/healthz")
    def ready():
        return {"api": "available"}

    @app.get("/v1/account")
    def account(digest: bytes = Depends(require_token)):
        return store.status(digest, int(time.time()))

    @app.post("/v1/trial")
    def trial(digest: bytes = Depends(require_token)):
        return store.start_trial(digest, int(time.time()))

    @app.get("/v1/nodes")
    def nodes(digest: bytes = Depends(require_token)):
        if not store.status(digest, int(time.time()))["managed_access"]:
            raise AccessRequired("Managed VPN access requires an active entitlement")
        return [{"region": settings.region, "endpoint": settings.endpoint, "protocol": "wireguard"}]

    @app.get("/v1/devices")
    def list_devices(digest: bytes = Depends(require_token)):
        return [{"id": d["id"], "public_key": d["public_key"], "addresses": tunnel_addresses(d["slot"])}
                for d in store.devices(digest)]

    @app.post("/v1/devices")
    def enroll(device: Enrollment, digest: bytes = Depends(require_token)):
        if device.public_key == settings.public_key:
            raise Conflict("The device key must differ from the server key")
        state = store.enroll(digest, device.public_key, int(time.time()))
        return {
            "id": state["id"],
            "addresses": tunnel_addresses(state["slot"]),
            "server_public_key": settings.public_key,
            "endpoint": settings.endpoint,
            "dns": settings.dns,
            "allowed_ips": ["0.0.0.0/0", "::/0"],
            "mtu": 1280,
            "persistent_keepalive": 25,
        }

    @app.delete("/v1/devices/{device_id}", status_code=204)
    def revoke(device_id: UUID, digest: bytes = Depends(require_token)):
        store.revoke(digest, device_id.hex)
        return Response(status_code=204)

    return app
