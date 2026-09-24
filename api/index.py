"""Vercel entry point: the same FastAPI app, served from precomputed scores."""

from app.main import app

__all__ = ["app"]
