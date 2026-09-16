"""
Router aggregation module.

This package splits the previously monolithic `routes.py` into cohesive modules
without changing behavior. Import `router` from this package to include all
handlers.
"""

from aiogram import Router

# Create the aggregate router and include feature routers from submodules
router = Router()

# Import submodule routers (side-effect: they register handlers on their module-level routers)
from . import analytics as _analytics  # noqa: E402,F401
from . import callbacks as _callbacks  # noqa: E402,F401
from . import formats as _formats  # noqa: E402,F401
from . import ingest as _ingest  # noqa: E402,F401
from . import maintenance as _maintenance  # noqa: E402,F401
from . import monitoring as _monitoring  # noqa: E402,F401
from . import performance as _performance  # noqa: E402,F401
from . import qa as _qa  # noqa: E402,F401
from . import report as _report  # noqa: E402,F401
from . import start_help as _start_help  # noqa: E402,F401
from . import system_config as _system_config  # noqa: E402,F401
from . import advanced_queries as _advanced_queries  # noqa: E402,F401
from . import security as _security  # noqa: E402,F401
from . import plugins as _plugins  # noqa: E402,F401
from . import admin as _admin  # noqa: E402,F401

# Include their routers into the aggregate router
router.include_router(_start_help.router)
router.include_router(_system_config.router)
router.include_router(_ingest.router)
router.include_router(_qa.router)
router.include_router(_performance.router)
router.include_router(_monitoring.router)
router.include_router(_callbacks.router)
router.include_router(_analytics.router)
router.include_router(_report.router)
router.include_router(_maintenance.router)
router.include_router(_formats.router)
router.include_router(_advanced_queries.router)
router.include_router(_security.router)
router.include_router(_plugins.router)
router.include_router(_admin.router)
