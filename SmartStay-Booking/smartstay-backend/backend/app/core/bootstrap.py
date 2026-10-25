"""Compatibility imports for the single MongoDB-backed bootstrap implementation."""

from app.admin.bootstrap import ensure_auth_indexes, ensure_roles, ensure_super_admin

__all__ = ["ensure_auth_indexes", "ensure_roles", "ensure_super_admin"]
