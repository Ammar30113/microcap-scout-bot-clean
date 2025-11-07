"""
Service layer for integrating external market data APIs.
"""

from .market_data import gather_symbol_insights

__all__ = ["gather_symbol_insights"]
