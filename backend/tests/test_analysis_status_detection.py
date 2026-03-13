"""Tests for analysis handler status detection and gap analysis trigger logic."""
import os
import pytest
from unittest.mock import MagicMock, patch

# Skip entire module if boto3 is not installed (analysis.handler imports boto3 at module level)
pytest.importorskip("boto3")

# Set a dummy AWS region before importing the handler (which initializes boto3 clients)
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


class TestSafeRegulationStatus:
    """Test safe_regulation_status() mapping."""

    def test_valid_proposed(self):
        from analysis.handler import safe_regulation_status
        from shared.models import RegulationStatus

        assert safe_regulation_status("proposed") == RegulationStatus.PROPOSED
        assert safe_regulation_status("proposed_rule") == RegulationStatus.PROPOSED
        assert safe_regulation_status("proposed rule") == RegulationStatus.PROPOSED

    def test_valid_final_rule(self):
        from analysis.handler import safe_regulation_status
        from shared.models import RegulationStatus

        assert safe_regulation_status("final_rule") == RegulationStatus.FINAL_RULE
        assert safe_regulation_status("final rule") == RegulationStatus.FINAL_RULE
        assert safe_regulation_status("final") == RegulationStatus.FINAL_RULE

    def test_valid_other_statuses(self):
        from analysis.handler import safe_regulation_status
        from shared.models import RegulationStatus

        assert safe_regulation_status("comment_period") == RegulationStatus.COMMENT_PERIOD
        assert safe_regulation_status("effective") == RegulationStatus.EFFECTIVE
        assert safe_regulation_status("archived") == RegulationStatus.ARCHIVED

    def test_unknown_fallback(self):
        from analysis.handler import safe_regulation_status
        from shared.models import RegulationStatus

        assert safe_regulation_status(None) == RegulationStatus.UNKNOWN
        assert safe_regulation_status("") == RegulationStatus.UNKNOWN
        assert safe_regulation_status("garbage_status") == RegulationStatus.UNKNOWN
        assert safe_regulation_status(123) == RegulationStatus.UNKNOWN

    def test_case_insensitive(self):
        from analysis.handler import safe_regulation_status
        from shared.models import RegulationStatus

        assert safe_regulation_status("PROPOSED") == RegulationStatus.PROPOSED
        assert safe_regulation_status("Final_Rule") == RegulationStatus.FINAL_RULE
        assert safe_regulation_status("  effective  ") == RegulationStatus.EFFECTIVE


class TestSafeProgramArea:
    """Test safe_program_area() normalization."""

    def test_valid_areas(self):
        from analysis.handler import safe_program_area

        assert safe_program_area(["MA", "PACE"]) == ["MA", "PACE"]
        assert safe_program_area(["Part D", "Medicaid", "General"]) == ["Part D", "Medicaid", "General"]

    def test_invalid_areas_filtered(self):
        from analysis.handler import safe_program_area

        assert safe_program_area(["MA", "InvalidArea", "PACE"]) == ["MA", "PACE"]

    def test_empty_and_none(self):
        from analysis.handler import safe_program_area

        assert safe_program_area(None) == []
        assert safe_program_area([]) == []
        assert safe_program_area("not_a_list") == []

    def test_all_invalid(self):
        from analysis.handler import safe_program_area

        assert safe_program_area(["Bogus", "Fake"]) == []


@pytest.mark.asyncio
class TestShouldRunGapAnalysis:
    """Test gap analysis trigger logic."""

    async def test_gap_analysis_requested_overrides(self):
        """Regulation with gap_analysis_requested=True always gets analyzed."""
        from analysis.handler import should_run_gap_analysis

        reg = MagicMock()
        reg.gap_analysis_requested = True
        reg.status = MagicMock(value="proposed")

        result = await should_run_gap_analysis(reg)
        assert result is True

    @patch("analysis.handler.get_gap_analysis_statuses")
    async def test_status_in_allowed_list(self, mock_get_statuses):
        """Regulation with status in the allowed list gets analyzed."""
        from analysis.handler import should_run_gap_analysis

        mock_get_statuses.return_value = ["final_rule", "effective"]

        reg = MagicMock()
        reg.gap_analysis_requested = False
        reg.status = MagicMock(value="final_rule")

        result = await should_run_gap_analysis(reg)
        assert result is True

    @patch("analysis.handler.get_gap_analysis_statuses")
    async def test_status_not_in_allowed_list(self, mock_get_statuses):
        """Regulation with status NOT in the allowed list gets skipped."""
        from analysis.handler import should_run_gap_analysis

        mock_get_statuses.return_value = ["final_rule", "effective"]

        reg = MagicMock()
        reg.gap_analysis_requested = False
        reg.status = MagicMock(value="proposed")

        result = await should_run_gap_analysis(reg)
        assert result is False

    @patch("analysis.handler.get_gap_analysis_statuses")
    async def test_unknown_status_skipped(self, mock_get_statuses):
        """Regulation with unknown status gets skipped by default."""
        from analysis.handler import should_run_gap_analysis

        mock_get_statuses.return_value = ["final_rule", "effective"]

        reg = MagicMock()
        reg.gap_analysis_requested = False
        reg.status = MagicMock(value="unknown")

        result = await should_run_gap_analysis(reg)
        assert result is False
