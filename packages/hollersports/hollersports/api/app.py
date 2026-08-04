"""FastAPI application factory for HollerSports packet API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hollersports.api.deps import RunStore, resolve_data_root
from hollersports.api.routes import router


def create_app(data_root: str | Path | None = None) -> FastAPI:
    """Build the paper-only operator API.

    Args:
        data_root: Store root for runs/ledgers. Defaults to HOLLER_DATA_ROOT or ``data/``.
    """
    root = resolve_data_root(data_root)
    store = RunStore(root)

    app = FastAPI(
        title="HollerSports Operator API",
        version="0.2.0",
        description="Paper-only sports market intelligence packets. No live capital.",
    )
    app.state.store = store
    app.state.data_root = root

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
