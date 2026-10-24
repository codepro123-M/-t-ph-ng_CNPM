"""The stable permission vocabulary. Roles in MongoDB select from these keys."""

PERMISSION_DOMAINS = {
    "booking": ("read", "update"),
    "poi": ("read", "create", "update", "delete"),
    "menu": ("read", "create", "update", "delete"),
    "user": ("read", "create", "update", "delete"),
    "role": ("read", "create", "update", "delete"),
    "analytics": ("read", "export"),
    "audit": ("read", "export"),
    "system": ("read", "update"),
    "owner": ("read", "approve", "reject", "suspend"),
    "content": ("read", "create", "update", "delete", "submit", "publish"),
}
PERMISSIONS = tuple(
    f"{domain}.{action}"
    for domain, actions in PERMISSION_DOMAINS.items()
    for action in actions
)
DEFAULT_ROLES = {
    "super_admin": {"priority": 0, "permissions": list(PERMISSIONS)},
    "admin": {
        "priority": 1,
        "permissions": [
            p for p in PERMISSIONS if p not in {"system.update", "role.delete"}
        ],
    },
    "poi_owner": {
        "priority": 10,
        "permissions": [p for p in PERMISSIONS if p.startswith("menu.")]
        + [
            "poi.read",
            "poi.update",
            "content.read",
            "content.create",
            "content.update",
            "content.delete",
            "content.submit",
        ],
    },
    "user": {"priority": 100, "permissions": ["poi.read", "menu.read", "content.read"]},
}
