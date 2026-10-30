"""
Data Sources package for Morning Intelligence Assistant.
"""
from src.data_sources.alpha_vantage import AlphaVantageSource
from src.data_sources.bank_of_canada import BankOfCanadaSource
from src.data_sources.coingecko import CoinGeckoSource
from src.data_sources.open_meteo import OpenMeteoSource
from src.data_sources.finance_calendar import FinanceCalendarSource
from src.data_sources.rss_news import RSSNewsSource
from src.data_sources.fred import FredSource
from src.data_sources.eia import EIASource
from src.data_sources.marketaux import MarketAuxSource
from src.data_sources.base import DataSourceBase, DataSourceError, RateLimitError
from src.data_sources.manager import DataSourceManager, data_source_manager

__all__ = [
    "AlphaVantageSource",
    "BankOfCanadaSource",
    "CoinGeckoSource",
    "OpenMeteoSource",
    "FinanceCalendarSource",
    "RSSNewsSource",
    "FredSource",
    "EIASource",
    "MarketAuxSource",
    "DataSourceBase",
    "DataSourceError",
    "RateLimitError",
    "DataSourceManager",
    "data_source_manager",
]