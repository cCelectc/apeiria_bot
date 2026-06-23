"""Unified core config routes."""

from fastapi import APIRouter

from apeiria.webui.routes.core_config import router as core_settings_router

router = APIRouter()
router.include_router(core_settings_router, prefix="")
