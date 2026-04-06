# ============================================================
#  handlers/callbacks/__init__.py  —  Aggregates callback routers
# ============================================================
from aiogram import Router

from .payment import router as payment_router

router = Router(name="callbacks")
router.include_router(payment_router)

__all__ = ["router"]
