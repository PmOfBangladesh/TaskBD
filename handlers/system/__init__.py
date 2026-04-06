# ============================================================
#  handlers/system/__init__.py  —  Aggregates system routers
# ============================================================
from aiogram import Router

from .ping      import router as ping_router
from .speedtest import router as speedtest_router
from .restart   import router as restart_router
from .logs      import router as logs_router

router = Router(name="system")

router.include_router(ping_router)
router.include_router(speedtest_router)
router.include_router(restart_router)
router.include_router(logs_router)

__all__ = ["router"]
