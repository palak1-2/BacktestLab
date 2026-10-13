"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.experiments import router
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Backtest Research Manager",
    description=(
        "An open-source research and experiment-management system for MT5 "
        "optimization/backtest research. "
        "This project is NOT financial advice or an automated trading system."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


app.include_router(router)
