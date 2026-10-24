"""Content implementation moved to app.content.service and app.content.sync.

The former RAM-backed db helpers and fake transaction mode were retired.
Use the FastAPI routes or the transaction-aware application services.
"""
