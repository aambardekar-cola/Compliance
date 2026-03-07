"""Federal Register API source for PACE-related regulations."""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

import httpx

from ingestion.sources.base import RegulatorySource, RawRegulation

logger = logging.getLogger(__name__)

# Federal Register API documentation: https://www.federalregister.gov/developers/api/v1
FEDERAL_REGISTER_API = "https://www.federalregister.gov/api/v1"

# Search terms relevant to PACE
PACE_SEARCH_TERMS = [
    "Programs of All-Inclusive Care for the Elderly",
    "PACE",
    "42 CFR 460",
    "42 CFR Part 460",
]

# Relevant agencies
RELEVANT_AGENCIES = [
    "centers-for-medicare-and-medicaid-services",
    "health-and-human-services-department",
]


class FederalRegisterSource(RegulatorySource):
    """Fetches PACE-related regulations from the Federal Register API."""

    @property
    def source_name(self) -> str:
        return "federal_register"

    async def fetch_latest(self, since: Optional[datetime] = None) -> list[RawRegulation]:
        """Fetch recent PACE-related documents from the Federal Register."""
        if since is None:
            since = datetime.utcnow() - timedelta(days=30)

        regulations = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Search by PACE-related terms and relevant agencies
            for term in PACE_SEARCH_TERMS:
                try:
                    docs = await self._search_documents(client, term, since)
                    regulations.extend(docs)
                except Exception as e:
                    logger.error(f"Error fetching Federal Register for term '{term}': {e}")

            # Also search by CFR citation
            try:
                cfr_docs = await self._search_by_cfr(client, "460", since)
                regulations.extend(cfr_docs)
            except Exception as e:
                logger.error(f"Error fetching by CFR reference: {e}")

        # Deduplicate by source_id
        seen = set()
        unique = []
        for reg in regulations:
            if reg.source_id not in seen:
                seen.add(reg.source_id)
                unique.append(reg)

        logger.info(f"Fetched {len(unique)} unique documents from Federal Register")
        return unique

    async def _search_documents(
        self,
        client: httpx.AsyncClient,
        search_term: str,
        since: datetime,
    ) -> list[RawRegulation]:
        """Search for documents by keyword."""
        params = {
            "conditions[term]": search_term,
            "conditions[publication_date][gte]": since.strftime("%m/%d/%Y"),
            "conditions[agencies][]": RELEVANT_AGENCIES,
            "conditions[type][]": ["RULE", "PRORULE", "NOTICE"],
            "fields[]": [
                "document_number",
                "title",
                "abstract",
                "body_html_url",
                "html_url",
                "publication_date",
                "effective_on",
                "comments_close_on",
                "agencies",
                "cfr_references",
                "type",
                "full_text_xml_url",
            ],
            "per_page": 50,
            "order": "newest",
        }

        response = await client.get(f"{FEDERAL_REGISTER_API}/documents.json", params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        regulations = []
        for doc in results:
            try:
                raw_reg = self._parse_document(doc)
                if raw_reg:
                    regulations.append(raw_reg)
            except Exception as e:
                logger.warning(f"Error parsing document {doc.get('document_number')}: {e}")

        return regulations

    async def _search_by_cfr(
        self,
        client: httpx.AsyncClient,
        cfr_part: str,
        since: datetime,
    ) -> list[RawRegulation]:
        """Search for documents by CFR reference."""
        params = {
            "conditions[cfr][title]": 42,  # Title 42: Public Health
            "conditions[cfr][part]": cfr_part,
            "conditions[publication_date][gte]": since.strftime("%m/%d/%Y"),
            "fields[]": [
                "document_number",
                "title",
                "abstract",
                "body_html_url",
                "html_url",
                "publication_date",
                "effective_on",
                "comments_close_on",
                "agencies",
                "cfr_references",
                "type",
            ],
            "per_page": 50,
            "order": "newest",
        }

        response = await client.get(f"{FEDERAL_REGISTER_API}/documents.json", params=params)
        response.raise_for_status()

        data = response.json()
        return [
            self._parse_document(doc)
            for doc in data.get("results", [])
            if self._parse_document(doc)
        ]

    def _parse_document(self, doc: dict) -> Optional[RawRegulation]:
        """Parse a Federal Register API document into a RawRegulation."""
        document_number = doc.get("document_number")
        title = doc.get("title", "")

        if not document_number or not title:
            return None

        # Map Federal Register type to our document_type
        fr_type = doc.get("type", "").upper()
        type_map = {
            "RULE": "final_rule",
            "PRORULE": "proposed_rule",
            "NOTICE": "notice",
        }
        document_type = type_map.get(fr_type, "notice")

        # Parse dates
        effective_date = self._parse_date(doc.get("effective_on"))
        published_date = self._parse_date(doc.get("publication_date"))
        comment_deadline = self._parse_date(doc.get("comments_close_on"))

        # Extract agencies
        agencies = [
            a.get("name", "")
            for a in doc.get("agencies", [])
            if a.get("name")
        ]

        # Extract CFR references
        cfr_refs = []
        for ref in doc.get("cfr_references", []):
            title_num = ref.get("title", "")
            part = ref.get("part", "")
            if title_num and part:
                cfr_refs.append(f"{title_num} CFR Part {part}")

        return RawRegulation(
            source=self.source_name,
            source_id=document_number,
            title=title,
            content=doc.get("abstract", "") or "",
            source_url=doc.get("html_url", ""),
            document_type=document_type,
            published_date=published_date,
            effective_date=effective_date,
            comment_deadline=comment_deadline,
            agencies=agencies,
            cfr_references=cfr_refs,
            summary=doc.get("abstract", "") or "",
        )

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """Parse a date string from the Federal Register API."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
