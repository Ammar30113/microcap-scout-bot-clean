from fastapi import FastAPI

from routes.health import router as health_router
from routes.products import router as products_router
from utils.logger import configure_logging
from utils.settings import get_settings

logger = configure_logging()

settings = get_settings()

app = FastAPI(
    title="Microcap Scout Bot",
    description="Microcap Scout Bot - clean FastAPI rebuild with Finviz, StockData, and Alpaca integrations.",
    version="0.1.0",
    contact={"name": "Microcap Scout Bot", "url": "https://github.com/Ammar30113/microcap-scout-bot-clean"},
)


@app.on_event("startup")
async def startup_event() -> None:
    # Simple startup hook to confirm settings load correctly.
    logger.info("Starting Microcap Scout Bot in %s mode", settings.environment)


app.include_router(health_router)
app.include_router(products_router)
