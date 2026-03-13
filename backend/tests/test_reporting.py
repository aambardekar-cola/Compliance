"""Tests for reporting module — scoring engine and report generation."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from reporting.scoring import (
    compute_module_scores,
    compute_overall_score,
    aggregate_week_metrics,
    build_gaps_summary,
    build_deadlines_summary,
)


# ---- Scoring Engine Tests ----


@pytest.mark.asyncio
async def test_compute_module_scores_empty(db_session):
    """No gaps → all modules score 100%."""
    scores = await compute_module_scores(db_session)
    assert scores == {}


@pytest.mark.asyncio
async def test_compute_overall_score_empty(db_session):
    """No gaps → overall score is 100%."""
    score = await compute_overall_score(db_session)
    assert score == 100.0


@pytest.mark.asyncio
async def test_compute_module_scores_with_gaps(db_session, seed_gaps_for_scoring):
    """Verify per-module scores with mixed resolved/open gaps."""
    scores = await compute_module_scores(db_session)
    # seed_gaps_for_scoring creates 2 resolved and 1 open for "Pharmacy"
    assert "Pharmacy" in scores
    # 2 resolved out of 3 = 66.7%
    assert scores["Pharmacy"] == pytest.approx(66.7, abs=0.1)


@pytest.mark.asyncio
async def test_compute_overall_score_with_gaps(db_session, seed_gaps_for_scoring):
    """Verify overall score with mixed gaps."""
    score = await compute_overall_score(db_session)
    # 2 resolved out of 3 total = 66.7%
    assert score == pytest.approx(66.7, abs=0.1)


@pytest.mark.asyncio
async def test_aggregate_week_metrics(db_session):
    """Verify weekly aggregation returns expected keys."""
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)
    metrics = await aggregate_week_metrics(db_session, week_start, now)

    assert "new_regulations" in metrics
    assert "gaps_identified" in metrics
    assert "gaps_resolved" in metrics
    assert "compliance_score" in metrics
    assert isinstance(metrics["compliance_score"], float)


@pytest.mark.asyncio
async def test_build_gaps_summary_empty(db_session):
    """No active gaps → returns empty message."""
    summary = await build_gaps_summary(db_session)
    assert "No active" in summary


@pytest.mark.asyncio
async def test_build_deadlines_summary_empty(db_session):
    """No upcoming deadlines → returns empty message."""
    summary = await build_deadlines_summary(db_session)
    assert "No upcoming" in summary


# ---- Report Generation Tests ----


@pytest.mark.asyncio
async def test_fallback_report():
    """Verify fallback report generation when Bedrock is unavailable."""
    from reporting.handler import _fallback_report

    metrics = {
        "new_regulations": 3,
        "gaps_identified": 5,
        "gaps_resolved": 2,
        "compliance_score": 72.5,
    }
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)
    week_end = now

    result = _fallback_report(metrics, week_start, week_end)

    assert "summary_html" in result
    assert "summary_plain" in result
    assert "3" in result["summary_html"]  # new_regulations
    assert "5" in result["summary_html"]  # gaps_identified
    assert "72.5%" in result["summary_html"]  # compliance_score
    assert result["risks"] == []
    assert result["highlights"] == []


def test_get_recipients_empty():
    """No REPORT_RECIPIENTS env var → empty list."""
    from reporting.handler import _get_recipients

    with patch.dict("os.environ", {}, clear=True):
        assert _get_recipients() == []


def test_get_recipients_configured():
    """REPORT_RECIPIENTS env var → parsed list."""
    from reporting.handler import _get_recipients

    with patch.dict("os.environ", {"REPORT_RECIPIENTS": "a@test.com, b@test.com"}):
        recipients = _get_recipients()
        assert recipients == ["a@test.com", "b@test.com"]


@pytest.mark.asyncio
async def test_generate_report_with_mock_bedrock(db_session):
    """End-to-end report generation with mocked Bedrock."""
    from reporting.handler import generate_report

    mock_llm_response = {
        "summary_html": "<h2>Test Report</h2>",
        "summary_plain": "Test Report",
        "metrics": {"new_regulations": 1},
        "risks": [{"title": "Test risk", "severity": "medium"}],
        "highlights": ["Completed test"],
    }

    with patch("reporting.handler.get_db_session") as mock_db_ctx, \
         patch("reporting.handler.invoke_llm", new_callable=AsyncMock, return_value=mock_llm_response), \
         patch("reporting.handler.aggregate_week_metrics", new_callable=AsyncMock, return_value={
             "new_regulations": 1, "gaps_identified": 2,
             "gaps_resolved": 1, "compliance_score": 85.0,
         }), \
         patch("reporting.handler.compute_module_scores", new_callable=AsyncMock, return_value={"Pharmacy": 90.0}), \
         patch("reporting.handler.build_gaps_summary", new_callable=AsyncMock, return_value="No gaps"), \
         patch("reporting.handler.build_deadlines_summary", new_callable=AsyncMock, return_value="No deadlines"):

        # Mock the async context manager for DB session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = "test-report-id"

        # When add is called, capture the report object
        def capture_report(obj):
            obj.id = "test-report-id"
        mock_session.add.side_effect = capture_report

        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await generate_report(send_email=False)

        assert result["status"] == "generated"
        assert result["id"] == "test-report-id"
        assert result["risks"] == [{"title": "Test risk", "severity": "medium"}]
        assert result["highlights"] == ["Completed test"]
