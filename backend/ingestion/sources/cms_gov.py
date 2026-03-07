"""CMS.gov sources for PACE-related regulations and guidance."""
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ingestion.sources.base import RegulatorySource, RawRegulation

logger = logging.getLogger(__name__)

# CMS Data API
CMS_DATA_API = "https://data.cms.gov/provider-data/api/1"

# CMS PACE-specific pages and endpoints
CMS_PACE_URLS = [
    "https://www.cms.gov/medicare/health-plans/pace",
    "https://www.cms.gov/regulations-and-guidance/legislation/cfr/index",
]


class CMSGovSource(RegulatorySource):
    """Fetches PACE-related regulatory data from CMS.gov."""

    @property
    def source_name(self) -> str:
        return "cms_gov"

    async def fetch_latest(self, since: Optional[datetime] = None) -> list[RawRegulation]:
        """Fetch latest PACE-related content from CMS.gov.

        Note: CMS.gov doesn't have a comprehensive API for regulatory documents.
        This implementation uses the CMS data API and supplements with
        known PACE-related endpoints. For production, consider:
        1. CMS HPMS system integration (if accessible)
        2. CMS.gov web scraping with appropriate rate limiting
        3. Federal Register API as the primary source (see federal_register.py)
        """
        if since is None:
            since = datetime.utcnow() - timedelta(days=30)

        regulations = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch from CMS newsroom / recent updates
            try:
                cms_regs = await self._fetch_cms_press_releases(client, since)
                regulations.extend(cms_regs)
            except Exception as e:
                logger.error(f"Error fetching CMS press releases: {e}")

            # Fetch PACE-specific memoranda and guidance
            try:
                pace_guidance = await self._fetch_pace_guidance(client, since)
                regulations.extend(pace_guidance)
            except Exception as e:
                logger.error(f"Error fetching PACE guidance: {e}")

        logger.info(f"Fetched {len(regulations)} documents from CMS.gov")
        return regulations

    async def _fetch_cms_press_releases(
        self,
        client: httpx.AsyncClient,
        since: datetime,
    ) -> list[RawRegulation]:
        """Fetch CMS press releases and fact sheets related to PACE.

        Uses CMS.gov search functionality to find PACE-related content.
        In production, this would be enhanced with more robust scraping
        or integration with CMS's content API.
        """
        regulations = []

        # CMS search API for PACE content
        search_url = "https://search.cms.gov/search"
        params = {
            "query": "PACE Programs All-Inclusive Care Elderly",
            "affiliate": "cms-main",
            "utf8": "✓",
        }

        try:
            response = await client.get(search_url, params=params, follow_redirects=True)
            if response.status_code == 200:
                # Note: In production, parse the HTML response to extract results
                # For now, this serves as the integration point
                logger.info("CMS search completed - production requires HTML parsing")
        except Exception as e:
            logger.warning(f"CMS search failed (non-critical): {e}")

        return regulations

    async def _fetch_pace_guidance(
        self,
        client: httpx.AsyncClient,
        since: datetime,
    ) -> list[RawRegulation]:
        """Fetch PACE-specific guidance documents from CMS.

        CMS publishes PACE-specific guidance through:
        1. PACE Manual chapters
        2. Health Plan Management System (HPMS) memoranda
        3. CMS transmittals
        4. MLN (Medicare Learning Network) articles

        In production, this would integrate with CMS's HPMS system
        for real-time access to PACE memoranda and guidance.
        """
        regulations = []

        # Known PACE guidance endpoints
        # These would be dynamically discovered in production
        pace_endpoints = [
            {
                "url": "https://www.cms.gov/medicare/health-plans/pace",
                "type": "guidance",
                "name": "CMS PACE Main Page",
            },
        ]

        for endpoint in pace_endpoints:
            try:
                response = await client.get(endpoint["url"], follow_redirects=True)
                if response.status_code == 200:
                    # In production: parse HTML for new guidance links and documents
                    logger.info(f"Checked PACE endpoint: {endpoint['name']}")
            except Exception as e:
                logger.warning(f"Failed to check {endpoint['name']}: {e}")

        return regulations
