"""Abstract base class for regulatory data sources."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class RawRegulation:
    """A raw regulation document fetched from a source."""
    source: str
    source_id: str
    title: str
    content: str
    source_url: str
    document_type: str  # "proposed_rule", "final_rule", "notice", "guidance"
    published_date: Optional[date] = None
    effective_date: Optional[date] = None
    comment_deadline: Optional[date] = None
    agencies: list[str] = field(default_factory=list)
    cfr_references: list[str] = field(default_factory=list)
    summary: str = ""


class RegulatorySource(ABC):
    """Abstract base class for regulatory data sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source."""
        ...

    @abstractmethod
    async def fetch_latest(self, since: Optional[datetime] = None) -> list[RawRegulation]:
        """Fetch the latest regulatory documents from this source.

        Args:
            since: Only fetch documents published after this datetime.
                   If None, fetch recent documents (implementation-defined timeframe).

        Returns:
            List of RawRegulation objects
        """
        ...
