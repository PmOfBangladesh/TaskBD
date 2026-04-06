# ============================================================
#  handlers/user/__init__.py  —  Aggregates all user routers
# ============================================================
from aiogram import Router

from .start    import router as start_router
from .profile  import router as profile_router
from .stats    import router as stats_router
from .withdraw import router as withdraw_router

router = Router(name="user")

# start / license first (catches generic text & /start)
router.include_router(start_router)
router.include_router(profile_router)
router.include_router(stats_router)
router.include_router(withdraw_router)

__all__ = ["router"]
