from datetime import datetime, timezone

from fastapi import APIRouter

from utils.settings import get_settings

router = APIRouter()


@router.get("/", summary="Health check", tags=["Health"])
@router.head("/", include_in_schema=False)
async def health_check() -> dict:
    """
    Basic health/status route for uptime checks.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": "microcap-scout-bot-clean",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
