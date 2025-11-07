from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.market_data import gather_symbol_insights
from utils.settings import get_settings

router = APIRouter()


class Product(BaseModel):
    name: str
    slug: str
    description: str
    integrations: List[str]
    sample_symbol: Optional[str] = Field(default=None, description="Symbol best suited for demoing this product")


class ProductListing(BaseModel):
    products: List[Product]
    sample_data: dict


PRODUCT_CATALOG: List[Product] = [
    Product(
        name="Microcap Screener",
        slug="microcap-screener",
        description="Async screener that blends Finviz filters with StockData fundamentals for near-real-time scans.",
        integrations=["Finviz", "StockData"],
        sample_symbol="IWM",
    ),
    Product(
        name="Momentum Radar",
        slug="momentum-radar",
        description="Multi-source momentum signals using Alpaca ticks married with Finviz heatmaps.",
        integrations=["Alpaca", "Finviz"],
        sample_symbol="QQQ",
    ),
]


@router.get(
    "/products.json",
    response_model=ProductListing,
    summary="Product catalog",
    tags=["Products"],
)
async def get_products(symbol: Optional[str] = Query(default=None, description="Override default symbol for sample data")) -> ProductListing:
    """
    Return the product catalog plus a blended data sample for the UI to render.
    """
    settings = get_settings()
    lookup_symbol = symbol or PRODUCT_CATALOG[0].sample_symbol or settings.default_symbol
    sample_data = await gather_symbol_insights(lookup_symbol)

    return ProductListing(products=PRODUCT_CATALOG, sample_data=sample_data)
