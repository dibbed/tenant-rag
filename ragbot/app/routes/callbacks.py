"""Main callbacks router - imports all callback handlers."""

from aiogram import Router

# Import all callback handlers
from .callbacks_main import router as main_callbacks_router
from .callbacks_admin import router as admin_callbacks_router
from .callbacks_security import router as security_callbacks_router
from .callbacks_analytics import router as analytics_callbacks_router
from .callbacks_monitoring import router as monitoring_callbacks_router
from .callbacks_plugins import router as plugins_callbacks_router

# Create main router
router = Router()

# Include all callback routers
router.include_router(main_callbacks_router)
router.include_router(admin_callbacks_router)
router.include_router(security_callbacks_router)
router.include_router(analytics_callbacks_router)
router.include_router(monitoring_callbacks_router)
router.include_router(plugins_callbacks_router)
