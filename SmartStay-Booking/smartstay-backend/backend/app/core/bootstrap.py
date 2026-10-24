"""Compatibility imports for the MongoDB-backed bootstrap and PII worker.

Runtime database access belongs in app.core.database; there is no in-memory
fallback or implicit default administrator.
"""

from app.admin.bootstrap import ensure_roles, ensure_super_admin
from app.core.retention import purge_expired_pii

__all__ = ["ensure_roles", "ensure_super_admin", "purge_expired_pii"]
