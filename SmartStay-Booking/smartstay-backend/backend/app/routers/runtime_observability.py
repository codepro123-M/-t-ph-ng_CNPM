"""Legacy import path; the active implementation uses MongoDB-backed services."""

from app.runtime_observability.router import router

__all__ = ["router"]
