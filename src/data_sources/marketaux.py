"""
MarketAux API source for financial news.
Free tier: 100 requests/month, requires API key.
Coverage: Global financial news with sentiment, entities, and filtering.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import DataSource, NewsItem


class MarketAuxSource(DataSourceBase):
    """MarketAux API client for financial news."""

    BASE_URL = "https://api.marketaux.com/v1"

    def __init__(self):
        super().__init__(
            name="MarketAux",
            base_url=self.BASE_URL,
            api_key=settings.marketaux_api_key,
            timeout=30.0,
            max_retries=2,
        )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "MorningIntelligence/1.0",
            "Accept": "application/json",
        }

    async def health_check(self) -> bool:
        """Check API availability."""
        try:
            params = {"api_token": self.api_key, "limit": 1}
            response = await self.client.get("/news/all", params=params)
            return response.status_code == 200
        except Exception:
            return False

    async def _fetch_news(
        self,
        countries: Optional[str] = None,
        entities: Optional[str] = None,
        topics: Optional[str] = None,
        industries: Optional[str] = None,
        languages: Optional[str] = "en,fr,ar",
        limit: int = 50,
        published_after: Optional[str] = None,
    ) -> List[NewsItem]:
        """Fetch news from MarketAux API."""
        try:
            params = {
                "api_token": self.api_key,
                "limit": limit,
                "language": languages,
            }
            if countries:
                params["countries"] = countries
            if entities:
                params["entities"] = entities
            if topics:
                params["topics"] = topics
            if industries:
                params["industries"] = industries
            if published_after:
                params["published_after"] = published_after

            response = await self.client.get("/news/all", params=params)
            response.raise_for_status()
            data = response.json()

            items = []
            for article in data.get("data", []):
                try:
                    # Parse published date
                    published_at_str = article.get("published_at")
                    if published_at_str:
                        # Handle various datetime formats
                        published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                    else:
                        published_at = datetime.now(timezone.utc)

                    # Build URL
                    url = article.get("url", "")

                    # Extract sentiment
                    sentiment = article.get("sentiment", {})
                    sentiment_score = None
                    if sentiment:
                        sentiment_score = sentiment.get("score")

                    # Extract entities
                    entities_list = []
                    for entity in article.get("entities", []):
                        entities_list.append(entity.get("name", ""))

                    items.append(NewsItem(
                        id=article.get("uuid", f"marketaux_{hash(url)}"),
                        headline=article.get("title", "").strip(),
                        summary=article.get("description", "").strip()[:500],
                        source="MarketAux",
                        url=url,
                        published_at=published_at,
                        category=article.get("topics", [{}])[0].get("name", "markets") if article.get("topics") else "markets",
                        regions=article.get("countries", []) if article.get("countries") else [],
                        tags=entities_list,
                        language=article.get("language", "en"),
                        is_verified=True,
                        metadata={
                            "sentiment_score": sentiment_score,
                            "source_name": article.get("source", ""),
                            "marketaux_id": article.get("uuid", ""),
                        },
                    ))
                except Exception:
                    continue

            return items

        except Exception as e:
            raise DataSourceError(f"Failed to fetch MarketAux news: {e}", self.name)

    # =========================================================================
    # REGIONAL NEWS
    # =========================================================================
    async def get_canadian_news(self, limit: int = 15) -> List[NewsItem]:
        """Get Canadian financial news."""
        return await self._fetch_news(
            countries="ca",
            languages="en,fr",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_us_news(self, limit: int = 15) -> List[NewsItem]:
        """Get US financial news."""
        return await self._fetch_news(
            countries="us",
            languages="en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_morocco_news(self, limit: int = 10) -> List[NewsItem]:
        """Get Moroccan financial news."""
        return await self._fetch_news(
            countries="ma",
            languages="fr,ar,en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        )

    async def get_europe_news(self, limit: int = 10) -> List[NewsItem]:
        """Get European financial news."""
        return await self._fetch_news(
            countries="gb,de,fr,it,es,nl,ch",
            languages="en,fr,de",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_global_news(self, limit: int = 10) -> List[NewsItem]:
        """Get global financial news."""
        return await self._fetch_news(
            languages="en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    # =========================================================================
    # TOPIC-BASED NEWS
    # =========================================================================
    async def get_central_bank_news(self, limit: int = 10) -> List[NewsItem]:
        """Get central bank news."""
        return await self._fetch_news(
            topics="central_bank,monetary_policy,interest_rates",
            languages="en,fr",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        )

    async def get_energy_news(self, limit: int = 10) -> List[NewsItem]:
        """Get energy/oil news."""
        return await self._fetch_news(
            topics="energy,oil,commodities",
            industries="energy,oil_gas",
            languages="en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_crypto_news(self, limit: int = 8) -> List[NewsItem]:
        """Get cryptocurrency news."""
        return await self._fetch_news(
            topics="cryptocurrency,bitcoin,ethereum",
            industries="crypto",
            languages="en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_housing_mortgage_news(self, limit: int = 8) -> List[NewsItem]:
        """Get housing and mortgage news."""
        return await self._fetch_news(
            topics="real_estate,mortgage,housing",
            industries="real_estate",
            languages="en,fr",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_banking_finance_news(self, limit: int = 8) -> List[NewsItem]:
        """Get banking and financial services news."""
        return await self._fetch_news(
            topics="banking,financial_services,earnings",
            industries="banking,financial_services",
            languages="en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    async def get_economic_indicators_news(self, limit: int = 8) -> List[NewsItem]:
        """Get economic indicators news (CPI, GDP, employment)."""
        return await self._fetch_news(
            topics="inflation,gdp,employment,economy",
            languages="en,fr",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    # =========================================================================
    # ENTITY-BASED NEWS
    # =========================================================================
    async def get_entity_news(self, entity_symbols: List[str], limit: int = 10) -> List[NewsItem]:
        """Get news for specific entities (e.g., BTC, AAPL, TSX)."""
        entities = ",".join(entity_symbols)
        return await self._fetch_news(
            entities=entities,
            languages="en",
            limit=limit,
            published_after=(datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        )

    # =========================================================================
    # CURATED NEWS FOR BRIEFING
    # =========================================================================
    async def get_curated_briefing_news(self, max_total: int = 30) -> List[NewsItem]:
        """Get curated news mix for morning briefing."""
        import asyncio

        # Fetch different categories in parallel
        results = await asyncio.gather(
            self.get_canadian_news(max_total // 5),
            self.get_us_news(max_total // 5),
            self.get_morocco_news(max_total // 10),
            self.get_europe_news(max_total // 10),
            self.get_central_bank_news(max_total // 10),
            self.get_energy_news(max_total // 10),
            self.get_housing_mortgage_news(max_total // 10),
            self.get_economic_indicators_news(max_total // 10),
            return_exceptions=True,
        )

        all_items = []
        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                # Log error but continue
                pass

        # Deduplicate by URL
        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        # Sort by relevance: central bank > energy > housing > economic > regional
        def relevance_score(item: NewsItem) -> float:
            score = 0.0
            # Recency
            hours_old = (datetime.now(timezone.utc) - item.published_at).total_seconds() / 3600
            score += max(0, 1 - hours_old / 48)
            # Category importance
            if item.category in ["central_bank", "monetary_policy", "interest_rates"]:
                score += 0.6
            elif item.category in ["energy", "oil", "commodities"]:
                score += 0.5
            elif item.category in ["real_estate", "mortgage", "housing"]:
                score += 0.5
            elif item.category in ["inflation", "gdp", "employment", "economy"]:
                score += 0.4
            elif item.category in ["banking", "financial_services", "earnings"]:
                score += 0.3
            elif item.category in ["markets"]:
                score += 0.2
            # Region relevance
            if "CA" in item.regions:
                score += 0.3
            if "MA" in item.regions:
                score += 0.2
            if "US" in item.regions:
                score += 0.2
            return score

        unique_items.sort(key=relevance_score, reverse=True)
        return unique_items[:max_total]