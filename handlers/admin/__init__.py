# ============================================================
#  handlers/admin/__init__.py  —  Aggregates all admin routers
# ============================================================
from aiogram import Router

from .panel       import router as panel_router
from .licenses    import router as licenses_router
from .reports     import router as reports_router
from .stats       import router as stats_router
from .users       import router as users_router
from .maintenance import router as maintenance_router
from .broadcast   import router as broadcast_router
from .pricing     import router as pricing_router
from .owner       import router as owner_router

router = Router(name="admin")

router.include_router(panel_router)
router.include_router(owner_router)       # owner commands before regular admin
router.include_router(licenses_router)
router.include_router(reports_router)
router.include_router(stats_router)
router.include_router(users_router)
router.include_router(maintenance_router)
router.include_router(broadcast_router)
router.include_router(pricing_router)

__all__ = ["router"]
