"""Legacy import path; the active implementation uses MongoDB-backed services."""

from app.ai_advisor.router import router

__all__ = ["router"]
