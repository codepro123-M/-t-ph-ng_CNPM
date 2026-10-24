"""Legacy import path; the active implementation uses MongoDB-backed services."""

from app.owner.router import router

__all__ = ["router"]
