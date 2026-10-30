"""
RSS News source for fetching financial news from multiple feeds.
Supports Canadian, US, Moroccan, and global financial news sources.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import feedparser
import httpx

from src.config import settings
from src.data_sources.base import DataSourceBase, DataSourceError
from src.models import DataSource, NewsItem


class RSSNewsSource(DataSourceBase):
    """RSS feed aggregator for financial news."""

    # Curated RSS feeds for financial news
    FEEDS = {
        # Canadian financial news
        "bank_of_canada": {
            "url": "https://www.bankofcanada.ca/feed/",
            "category": "central_bank",
            "regions": ["CA"],
            "language": "en",
        },
        "globe_investing": {
            "url": "https://www.theglobeandmail.com/business/investing/rss/",
            "category": "markets",
            "regions": ["CA"],
            "language": "en",
        },
        "financial_post": {
            "url": "https://financialpost.com/category/markets/feed/",
            "category": "markets",
            "regions": ["CA"],
            "language": "en",
        },
        "bnn_bloomberg": {
            "url": "https://www.bnnbloomberg.ca/rss/markets",
            "category": "markets",
            "regions": ["CA"],
            "language": "en",
        },
        "cbc_business": {
            "url": "https://www.cbc.ca/cmlink/rss-business",
            "category": "business",
            "regions": ["CA"],
            "language": "en",
        },

        # US financial news
        "reuters_business": {
            "url": "https://feeds.reuters.com/reuters/businessNews",
            "category": "business",
            "regions": ["US", "global"],
            "language": "en",
        },
        "reuters_markets": {
            "url": "https://feeds.reuters.com/reuters/marketsNews",
            "category": "markets",
            "regions": ["US", "global"],
            "language": "en",
        },
        "bloomberg_markets": {
            "url": "https://feeds.bloomberg.com/markets/news.rss",
            "category": "markets",
            "regions": ["US", "global"],
            "language": "en",
        },
        "wsj_markets": {
            "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "category": "markets",
            "regions": ["US", "global"],
            "language": "en",
        },
        "ft_markets": {
            "url": "https://www.ft.com/markets?format=rss",
            "category": "markets",
            "regions": ["global", "EU"],
            "language": "en",
        },

        # Moroccan financial news
        "bank_al_maghrib": {
            "url": "https://www.bkam.ma/en/Press-releases/rss",
            "category": "central_bank",
            "regions": ["MA"],
            "language": "fr",
        },
        "hcp_morocco": {
            "url": "https://www.hcp.ma/rss.xml",
            "category": "statistics",
            "regions": ["MA"],
            "language": "fr",
        },
        "medias24_economie": {
            "url": "https://medias24.com/sujet/economie/rss/",
            "category": "economy",
            "regions": ["MA"],
            "language": "fr",
        },

        # Energy/Oil specific
        "eia_today_in_energy": {
            "url": "https://www.eia.gov/todayinenergy/rss.xml",
            "category": "energy",
            "regions": ["US", "global"],
            "language": "en",
        },
        "opec_news": {
            "url": "https://www.opec.org/opec_web/en/press_room/3429.htm",
            "category": "energy",
            "regions": ["global"],
            "language": "en",
        },
    }

    def __init__(self):
        super().__init__(
            name="RSS News Aggregator",
            base_url="",  # Not used for RSS
            api_key=None,
            timeout=30.0,
            max_retries=2,
        )

    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "MorningIntelligence/1.0 (+https://github.com/user/morning-intelligence)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        }

    async def health_check(self) -> bool:
        """Check if at least one feed is accessible."""
        try:
            # Test with a reliable feed
            await self._fetch_feed(self.FEEDS["reuters_business"]["url"])
            return True
        except Exception:
            return False

    async def _fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse a single RSS feed."""
        try:
            response = await self.client.get(url, timeout=15.0)
            response.raise_for_status()
            return feedparser.parse(response.text)
        except Exception as e:
            raise DataSourceError(f"Failed to fetch feed {url}: {e}", self.name)

    def _parse_entry(self, entry: feedparser.FeedParserDict, feed_info: Dict) -> Optional[NewsItem]:
        """Parse a feed entry into a NewsItem."""
        try:
            # Get published date
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                published_at = datetime(*published[:6])
            else:
                published_at = datetime.now(timezone.utc)

            # Get summary/content
            summary = entry.get("summary", "") or entry.get("description", "")
            # Clean HTML tags from summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary[:500]  # Truncate

            # Generate ID from link
            link = entry.get("link", "")
            news_id = link.split("/")[-1] if link else str(hash(entry.get("title", "")))

            return NewsItem(
                id=news_id,
                headline=entry.get("title", "").strip(),
                summary=summary.strip(),
                source=feed_info.get("category", "unknown"),
                url=link,
                published_at=published_at,
                category=feed_info.get("category", "general"),
                regions=feed_info.get("regions", []),
                language=feed_info.get("language", "en"),
                is_verified=False,
            )
        except Exception:
            return None

    async def fetch_feed(self, feed_key: str, max_items: int = 10) -> List[NewsItem]:
        """Fetch news from a specific feed."""
        if feed_key not in self.FEEDS:
            raise DataSourceError(f"Unknown feed: {feed_key}", self.name)

        feed_info = self.FEEDS[feed_key]
        feed_data = await self._fetch_feed(feed_info["url"])

        items = []
        for entry in feed_data.entries[:max_items]:
            parsed = self._parse_entry(entry, feed_info)
            if parsed:
                items.append(parsed)

        return items

    async def fetch_all_feeds(
        self,
        categories: List[str] = None,
        regions: List[str] = None,
        max_per_feed: int = 5,
        hours_back: int = 24,
    ) -> List[NewsItem]:
        """Fetch news from all configured feeds with filtering."""
        all_items = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        for feed_key, feed_info in self.FEEDS.items():
            # Filter by category
            if categories and feed_info["category"] not in categories:
                continue
            # Filter by region
            if regions and not any(r in feed_info["regions"] for r in regions):
                continue

            try:
                items = await self.fetch_feed(feed_key, max_items=max_per_feed)
                # Filter by time
                items = [item for item in items if item.published_at >= cutoff_time]
                all_items.extend(items)
            except Exception:
                continue  # Skip failed feeds

        # Sort by published date (newest first)
        all_items.sort(key=lambda x: x.published_at, reverse=True)
        return all_items

    async def get_canadian_news(self, max_items: int = 20) -> List[NewsItem]:
        """Get Canadian financial news."""
        return await self.fetch_all_feeds(
            regions=["CA"],
            max_per_feed=max_items // 5,
            hours_back=24,
        )

    async def get_us_global_news(self, max_items: int = 20) -> List[NewsItem]:
        """Get US and global financial news."""
        return await self.fetch_all_feeds(
            regions=["US", "global"],
            max_per_feed=max_items // 6,
            hours_back=24,
        )

    async def get_morocco_news(self, max_items: int = 10) -> List[NewsItem]:
        """Get Moroccan financial news."""
        return await self.fetch_all_feeds(
            regions=["MA"],
            max_per_feed=max_items // 3,
            hours_back=48,  # Moroccan feeds may update less frequently
        )

    async def get_energy_news(self, max_items: int = 10) -> List[NewsItem]:
        """Get energy/oil specific news."""
        return await self.fetch_all_feeds(
            categories=["energy"],
            max_per_feed=max_items // 2,
            hours_back=24,
        )

    async def get_central_bank_news(self, max_items: int = 10) -> List[NewsItem]:
        """Get central bank news."""
        return await self.fetch_all_feeds(
            categories=["central_bank"],
            max_per_feed=max_items // 3,
            hours_back=48,
        )

    async def get_top_news(
        self,
        max_total: int = 30,
        canadian_weight: float = 0.4,
        us_global_weight: float = 0.4,
        morocco_weight: float = 0.1,
        energy_weight: float = 0.1,
    ) -> List[NewsItem]:
        """Get curated top news for briefing with regional weighting."""
        all_items = []

        # Canadian news
        ca_items = await self.get_canadian_news(int(max_total * canadian_weight))
        all_items.extend(ca_items)

        # US/Global news
        us_items = await self.get_us_global_news(int(max_total * us_global_weight))
        all_items.extend(us_items)

        # Morocco news
        ma_items = await self.get_morocco_news(int(max_total * morocco_weight))
        all_items.extend(ma_items)

        # Energy news
        energy_items = await self.get_energy_news(int(max_total * energy_weight))
        all_items.extend(energy_items)

        # Deduplicate by headline similarity
        seen_headlines = set()
        unique_items = []
        for item in all_items:
            headline_key = item.headline.lower().strip()[:50]
            if headline_key not in seen_headlines:
                seen_headlines.add(headline_key)
                unique_items.append(item)

        # Sort by relevance: prioritize recent, high-impact categories
        def relevance_score(item: NewsItem) -> float:
            score = 0.0
            # Recency (0-1)
            hours_old = (datetime.now(timezone.utc) - item.published_at).total_seconds() / 3600
            score += max(0, 1 - hours_old / 48)
            # Category importance
            if item.category in ["central_bank", "markets", "energy"]:
                score += 0.5
            elif item.category in ["business", "economy"]:
                score += 0.3
            # Region relevance for user
            if "CA" in item.regions:
                score += 0.3
            if "MA" in item.regions:
                score += 0.2
            return score

        unique_items.sort(key=relevance_score, reverse=True)
        return unique_items[:max_total]