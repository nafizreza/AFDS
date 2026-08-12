from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.router import create_router
from .core.config import PROJECT_ROOT
from .domain.types import ApiError
from .orchestration.controller import AFDSController


controller = AFDSController()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await controller.startup()
    try:
        yield
    finally:
        await controller.shutdown()


app = FastAPI(
    title="AFDS Hardware API",
    version="1.0.0",
    description="Authoritative hardware/manual API for the Adulterated Fruit Detection System",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(create_router(controller))


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}, "state": controller.snapshot()})


frontend_dist = PROJECT_ROOT / "frontend" / "dist"
assets = frontend_dist / "assets"
if assets.exists():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str) -> FileResponse:
    index = frontend_dist / "index.html"
    if not index.exists():
        raise ApiError("FRONTEND_NOT_BUILT", "Build the frontend or use the Vite development server", 503)
    candidate = frontend_dist / path
    if candidate.is_file() and frontend_dist in candidate.resolve().parents:
        return FileResponse(candidate)
    return FileResponse(index)

