"""Admin API routes package.

All admin endpoints live under /admin/* and require appropriate
admin.* permissions. Import and register the sub-routers from main.py.
"""

from app.routes.admin import config, permissions

__all__ = ["config", "permissions"]
