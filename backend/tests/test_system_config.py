"""Tests for SystemConfig CRUD operations."""
import pytest
import uuid


class TestSystemConfig:
    """Test the SystemConfig model and its API interactions."""

    def test_system_config_model_creation(self):
        """Verify SystemConfig model can be instantiated with required fields."""
        from shared.models import SystemConfig
        
        config = SystemConfig(
            key="gap_analysis_statuses",
            value=["final_rule", "effective"],
            description="Test config",
        )
        assert config.key == "gap_analysis_statuses"
        assert config.value == ["final_rule", "effective"]
        assert config.description == "Test config"

    def test_system_config_model_json_value(self):
        """Verify SystemConfig can store various JSON value types."""
        from shared.models import SystemConfig
        
        # List
        config_list = SystemConfig(key="list_config", value=["a", "b"])
        assert config_list.value == ["a", "b"]
        
        # Dict
        config_dict = SystemConfig(key="dict_config", value={"key": "val"})
        assert config_dict.value == {"key": "val"}
        
        # Boolean
        config_bool = SystemConfig(key="bool_config", value=True)
        assert config_bool.value is True

    def test_system_config_model_optional_description(self):
        """Verify description is optional."""
        from shared.models import SystemConfig
        
        config = SystemConfig(
            key="no_desc",
            value=["test"],
        )
        assert config.key == "no_desc"
        assert config.description is None


@pytest.mark.asyncio
class TestSystemConfigAPI:
    """Test SystemConfig API serialization contract."""

    async def test_serialize_config(self):
        """Verify _serialize_config produces expected output shape."""
        from api.routes.system_config import _serialize_config
        from shared.models import SystemConfig
        from datetime import datetime

        config = SystemConfig(
            id=uuid.uuid4(),
            key="gap_analysis_statuses",
            value=["final_rule", "effective"],
            description="Test desc",
        )
        config.updated_at = datetime(2026, 3, 10, 12, 0, 0)

        result = _serialize_config(config)
        assert result["key"] == "gap_analysis_statuses"
        assert result["value"] == ["final_rule", "effective"]
        assert result["description"] == "Test desc"
        assert result["updated_at"] == "2026-03-10T12:00:00"
        assert "id" in result
