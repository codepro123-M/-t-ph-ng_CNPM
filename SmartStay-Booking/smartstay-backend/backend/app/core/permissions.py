"""One dotted permission catalog shared by API, role seeds and React."""

PERMISSION_DOMAINS = {
    "poi": ["poi.read", "poi.create", "poi.update", "poi.delete"],
    "menu": ["menu.read", "menu.create", "menu.update", "menu.delete"],
    "user": ["user.read", "user.create", "user.update", "user.delete"],
    "role": ["role.read", "role.create", "role.update", "role.delete"],
    "analytics": ["analytics.read", "analytics.export"],
    "audit": ["audit.read", "audit.export"],
    "system": ["system.read", "system.update"],
    "owner": ["owner.read", "owner.approve", "owner.reject", "owner.suspend"],
    "content": [
        "content.read",
        "content.create",
        "content.update",
        "content.delete",
        "content.submit",
        "content.publish",
    ],
    "booking": ["booking.read", "booking.update"],
}
PERMISSIONS = [
    permission for values in PERMISSION_DOMAINS.values() for permission in values
]
PERMISSIONS_BY_DOMAIN = PERMISSION_DOMAINS
ALL_PERMISSIONS = PERMISSIONS

DEFAULT_ROLES = {
    "super_admin": {
        "name": "super_admin",
        "priority": 0,
        "permissions": list(PERMISSIONS),
    },
    "admin": {
        "name": "admin",
        "priority": 1,
        "permissions": [
            p for p in PERMISSIONS if p not in {"system.update", "role.delete"}
        ],
    },
    "poi_owner": {
        "name": "poi_owner",
        "priority": 10,
        "permissions": [
            "poi.read",
            "poi.update",
            "menu.read",
            "menu.create",
            "menu.update",
            "menu.delete",
            "content.read",
            "content.create",
            "content.update",
            "content.delete",
            "content.submit",
        ],
    },
    "user": {
        "name": "user",
        "priority": 100,
        "permissions": ["poi.read", "menu.read", "content.read"],
    },
}
