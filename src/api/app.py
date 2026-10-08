import secrets
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.models import Decision, StartAnalysis
from src.api.service import ApiError, Service
from src.api.settings import Settings


def create_app(settings=None, service=None, start_worker=True):
    settings = settings or Settings.from_env()
    service = service or Service(settings)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            service.start_worker()
        try:
            yield
        finally:
            if start_worker:
                service.stop_worker()

    app = FastAPI(title="Runbook updater API", version="1.3.0", lifespan=lifespan)
    app.state.service = service

    def authorize(authorization: Annotated[str | None, Header()] = None):
        supplied = (authorization or "").removeprefix("Bearer ")
        if not (authorization or "").startswith("Bearer ") or not secrets.compare_digest(supplied.encode(), settings.token.encode()):
            raise HTTPException(401, "Invalid service token", headers={"WWW-Authenticate": "Bearer"})

    def idempotency_key(key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
        if not key or not key.strip() or len(key) > 200:
            raise HTTPException(422, "A nonempty Idempotency-Key header of at most 200 characters is required")
        return key

    @app.exception_handler(ApiError)
    async def api_error_handler(request, error):
        return error_response(error.status, error.message)

    def error_response(status, message, headers=None):
        codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 422: "INVALID_REQUEST"}
        return JSONResponse(status_code=status, headers=headers,
                            content={"error": {"code": codes.get(status, "REQUEST_FAILED"), "message": message}})

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request, error):
        return error_response(error.status_code, str(error.detail), error.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, error):
        fields = ", ".join(".".join(str(part) for part in item["loc"]) for item in error.errors())
        return error_response(422, f"Invalid request fields: {fields}")

    @app.get("/health")
    def health():
        return {"status": "ok", "storage": "sqlite", "retrieval": "disabled"}

    @app.post("/v1/analyses", dependencies=[Depends(authorize)], status_code=202)
    def start(body: StartAnalysis, key: str = Depends(idempotency_key)):
        status, response = service.start_analysis(body.model_dump(mode="json"), key)
        return JSONResponse(status_code=status, content=response)

    @app.get("/v1/analyses/{analysis_id}", dependencies=[Depends(authorize)])
    def get(analysis_id: str):
        return service.get_analysis(analysis_id)

    @app.post("/v1/analyses/{analysis_id}/decisions", dependencies=[Depends(authorize)], status_code=202)
    def decide(analysis_id: str, body: Decision, key: str = Depends(idempotency_key)):
        status, response = service.decide(analysis_id, body.model_dump(mode="json"), key)
        return JSONResponse(status_code=status, content=response)

    # Swagger shows the same response schemas and bearer security as the App.
    generated = app.openapi()
    contract = json.loads((Path(__file__).resolve().parents[2] / "openapi.json").read_text())
    generated["components"].update(contract["components"])
    generated["paths"].update(contract["paths"])
    generated["security"] = contract["security"]
    generated["paths"]["/health"]["get"]["security"] = []
    app.openapi_schema = generated
    return app
