import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scripts.seed_urls import seed_data, SEED_URLS

@pytest.mark.asyncio
async def test_seed_urls_idempotency():
    """Verify that seed_data prevents duplicate URLs and calls session.add correctly."""
    
    # Mock database session
    mock_session = AsyncMock()
    
    # Mock the select result: first one exists, others don't
    mock_result = MagicMock()
    # Let's say the first URL in SEED_URLS already exists in DB
    mock_result.scalars.return_value.first.side_effect = [MagicMock(), None, None, None, None, None]
    
    mock_session.execute.return_value = mock_result
    
    with patch("scripts.seed_urls.get_db_session") as mock_get_db:
        mock_get_db.return_value.__aenter__.return_value = mock_session
        
        await seed_data()
        
        # Should have checked every URL in SEED_URLS
        assert mock_session.execute.call_count == len(SEED_URLS)
        
        # Should have called add for (total - 1 existing)
        assert mock_session.add.call_count == len(SEED_URLS) - 1
        
        # Should have committed once
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_seed_urls_error_handling():
    """Verify that if an error occurs, it is raised (or handled) and session is closed."""
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB Error")
    
    with patch("scripts.seed_urls.get_db_session") as mock_get_db:
        mock_get_db.return_value.__aenter__.return_value = mock_session
        
        with pytest.raises(Exception, match="DB Error"):
            await seed_data()
