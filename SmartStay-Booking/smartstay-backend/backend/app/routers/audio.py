"""Legacy import path; the active implementation uses MongoDB-backed services."""

from app.audio.router import router

__all__ = ["router"]
