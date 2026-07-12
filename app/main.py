"""ChainGuard API — five routes, no more.

Everything expensive (model, calibrator, explainer, feature table) loads
once in `lifespan`, before the server accepts traffic. Nothing in this
module accuses anyone of anything; it reports scores and reasons.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    ADDRESS_PATTERN,
    HealthResponse,
    ModelInfoResponse,
    ScoreRequest,
    ScoreResponse,
)
from app.scoring import ModelBundle

MODEL_NOT_LOADED = {
    "message": "The scoring model isn't loaded.",
    "hint": "Run `make train`, then restart.",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bundle = ModelBundle.load()
    yield


app = FastAPI(title="ChainGuard", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    content = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail), "hint": ""}
    return JSONResponse(status_code=exc.status_code, content=content)


def _bundle(request: Request) -> ModelBundle:
    bundle: ModelBundle | None = request.app.state.bundle
    if bundle is None:
        raise HTTPException(status_code=503, detail=MODEL_NOT_LOADED)
    return bundle


@app.post("/api/score", response_model=ScoreResponse)
async def score(payload: ScoreRequest, request: Request) -> dict:
    if not re.fullmatch(ADDRESS_PATTERN, payload.address):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "That doesn't look like an Ethereum address.",
                "hint": "An address is `0x` followed by 40 hex characters.",
            },
        )

    bundle = _bundle(request)
    result = bundle.score_address(payload.address)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "This address isn't in the demo dataset.",
                "hint": "Try one of the example addresses.",
            },
        )
    return result


@app.get("/api/model/info", response_model=ModelInfoResponse)
async def model_info(request: Request) -> dict:
    bundle = _bundle(request)
    return {**bundle.metrics, "thresholds": bundle.thresholds}


@app.get("/api/examples")
async def examples(request: Request) -> dict:
    bundle = _bundle(request)
    return {"examples": bundle.examples()}


@app.get("/health", response_model=HealthResponse)
async def health() -> dict:
    return {"status": "up"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
