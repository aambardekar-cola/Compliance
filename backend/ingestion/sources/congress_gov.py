"""Congress.gov API source for PACE-related legislation."""
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ingestion.sources.base import RegulatorySource, RawRegulation

logger = logging.getLogger(__name__)

# Congress.gov API (requires API key)
CONGRESS_API = "https://api.congress.gov/v3"


class CongressGovSource(RegulatorySource):
    """Fetches PACE-related bills and legislation from Congress.gov."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def source_name(self) -> str:
        return "congress_gov"

    async def fetch_latest(self, since: Optional[datetime] = None) -> list[RawRegulation]:
        """Fetch PACE-related legislation from Congress.gov API."""
        if not self.api_key:
            logger.warning("Congress.gov API key not configured, skipping source")
            return []

        if since is None:
            since = datetime.utcnow() - timedelta(days=90)

        regulations = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            search_terms = [
                "PACE program elderly",
                "Programs All-Inclusive Care Elderly",
                "Medicare PACE",
            ]

            for term in search_terms:
                try:
                    bills = await self._search_bills(client, term, since)
                    regulations.extend(bills)
                except Exception as e:
                    logger.error(f"Error searching Congress.gov for '{term}': {e}")

        # Deduplicate
        seen = set()
        unique = []
        for reg in regulations:
            if reg.source_id not in seen:
                seen.add(reg.source_id)
                unique.append(reg)

        logger.info(f"Fetched {len(unique)} documents from Congress.gov")
        return unique

    async def _search_bills(
        self,
        client: httpx.AsyncClient,
        query: str,
        since: datetime,
    ) -> list[RawRegulation]:
        """Search for bills related to PACE."""
        params = {
            "query": query,
            "fromDateTime": since.strftime("%Y-%m-%dT00:00:00Z"),
            "limit": 25,
            "api_key": self.api_key,
        }

        response = await client.get(f"{CONGRESS_API}/bill", params=params)
        response.raise_for_status()

        data = response.json()
        bills = data.get("bills", [])

        regulations = []
        for bill in bills:
            try:
                reg = RawRegulation(
                    source=self.source_name,
                    source_id=bill.get("number", ""),
                    title=bill.get("title", ""),
                    content=bill.get("title", ""),  # Would fetch full text in production
                    source_url=bill.get("url", ""),
                    document_type="legislation",
                    published_date=self._parse_date(bill.get("introducedDate")),
                    agencies=["Congress"],
                    summary=bill.get("title", ""),
                )
                regulations.append(reg)
            except Exception as e:
                logger.warning(f"Error parsing bill: {e}")

        return regulations

    @staticmethod
    def _parse_date(date_str: Optional[str]):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            return None
