"""Content services live in app.content; there is no in-memory storage fallback."""

from app.content.service import haversine

__all__ = ["haversine"]
