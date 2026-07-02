"""Renewable Trade Monitor — FastAPI app.

Run:  uvicorn app.main:app --reload      (or: python -m app)
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .api import meta, signals, trade

app = FastAPI(title="Renewable Trade Monitor", version="0.1.0")
app.include_router(meta.router)
app.include_router(trade.router)
app.include_router(signals.router)
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
