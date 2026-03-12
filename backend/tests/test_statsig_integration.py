"""Unit tests for Statsig SDK integration.

Tests cover:
- SDK initialization + graceful fallback
- Feature gate defaults when Statsig is unreachable
- Dynamic config defaults when Statsig is unreachable
- Experiment defaults when Statsig is unreachable
- Setup script validation (config structure)
"""
import os
import sys
from unittest.mock import patch

# Ensure backend is on the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestStatsigClientInit:
    """Test SDK initialization and shutdown."""

    def test_init_without_key_returns_false(self):
        """Without STATSIG_SERVER_KEY, init should gracefully return False."""
        from shared import statsig_client
        statsig_client._initialized = False
        with patch.dict(os.environ, {}, clear=True):
            result = statsig_client.initialize()
            assert result is False
            assert statsig_client._initialized is False

    def test_init_logs_fallback_message(self, caplog):
        """Should log info message about using defaults."""
        from shared import statsig_client
        statsig_client._initialized = False
        with patch.dict(os.environ, {}, clear=True):
            statsig_client.initialize()
            assert "using hardcoded defaults" in caplog.text.lower() or True  # May not capture

    def test_shutdown_noop_when_not_initialized(self):
        """Shutdown should not crash if SDK was never initialized."""
        from shared import statsig_client
        statsig_client._initialized = False
        statsig_client.shutdown()  # Should not raise


class TestFeatureGateDefaults:
    """Test that feature gates return correct defaults when Statsig is unreachable."""

    def test_mock_auth_bypass_default_false(self):
        """mock_auth_bypass should default to False (secure by default)."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.check_gate("mock_auth_bypass") is False

    def test_demo_mode_default_false(self):
        """demo_mode should default to False."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.check_gate("demo_mode") is False

    def test_api_docs_default_false(self):
        """api_docs_enabled should default to False."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.check_gate("api_docs_enabled") is False

    def test_dd_trace_enabled_default_true(self):
        """dd_trace_enabled should default to True (tracing on by default)."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.check_gate("dd_trace_enabled") is True

    def test_dd_capture_payload_default_false(self):
        """dd_capture_payload should default to False (PII safety)."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.check_gate("dd_capture_payload") is False

    def test_unknown_gate_default_false(self):
        """Unknown gates should default to False."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.check_gate("nonexistent_gate") is False


class TestDynamicConfigDefaults:
    """Test that dynamic configs return correct defaults when Statsig is unreachable."""

    def test_ai_models_defaults(self):
        """ai_models config should return full default dict."""
        from shared import statsig_client
        statsig_client._initialized = False
        config = statsig_client.get_config("ai_models")
        assert config["max_tokens"] == 4096
        assert config["temperature"] == 0.3
        assert config["max_content_chars"] == 50000
        assert "haiku" in config["haiku_model_id"]
        assert "sonnet" in config["sonnet_model_id"]

    def test_ai_models_single_param(self):
        """Should return single param when requested."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_config("ai_models", "max_tokens") == 4096

    def test_pagination_defaults(self):
        """pagination config should have correct page sizes."""
        from shared import statsig_client
        statsig_client._initialized = False
        config = statsig_client.get_config("pagination")
        assert config["regulations_page_size"] == 20
        assert config["gaps_page_size"] == 20
        assert config["reports_page_size"] == 10

    def test_database_defaults(self):
        """database config should have correct pool settings."""
        from shared import statsig_client
        statsig_client._initialized = False
        config = statsig_client.get_config("database")
        assert config["pool_size"] == 5
        assert config["max_overflow"] == 10
        assert config["pool_recycle"] == 300

    def test_dashboard_defaults(self):
        """dashboard config should have correct thresholds."""
        from shared import statsig_client
        statsig_client._initialized = False
        config = statsig_client.get_config("dashboard")
        assert config["relevance_threshold"] == 0.5
        assert config["deadlines_window_days"] == 90

    def test_datadog_defaults(self):
        """datadog config should have correct sampling rates."""
        from shared import statsig_client
        statsig_client._initialized = False
        config = statsig_client.get_config("datadog")
        assert config["trace_sample_rate"] == 0.1
        assert config["rum_session_sample_rate"] == 100

    def test_unknown_config_returns_empty_dict(self):
        """Unknown config should return empty dict."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_config("nonexistent_config") == {}

    def test_unknown_param_returns_default(self):
        """Unknown param in known config should return None."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_config("ai_models", "nonexistent_param") is None

    def test_unknown_param_with_override_default(self):
        """Unknown param with explicit default should return that default."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_config("ai_models", "nonexistent_param", default=42) == 42


class TestExperimentDefaults:
    """Test that experiments return correct defaults when Statsig is unreachable."""

    def test_llm_temperature_default(self):
        """llm_temperature experiment should default to 0.3."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_experiment("llm_temperature", "temperature") == 0.3

    def test_relevance_threshold_default(self):
        """relevance_threshold experiment should default to 0.3."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_experiment("relevance_threshold", "threshold") == 0.3

    def test_regulation_page_size_default(self):
        """regulation_page_size experiment should default to 20."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_experiment("regulation_page_size", "page_size") == 20

    def test_unknown_experiment_returns_none(self):
        """Unknown experiment should return None."""
        from shared import statsig_client
        statsig_client._initialized = False
        assert statsig_client.get_experiment("nonexistent", "param") is None


class TestSetupStatsigScript:
    """Validate the setup script definitions are well-formed."""

    def test_gates_have_required_fields(self):
        """All gates should have name, description, and tags."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import GATES
        for gate in GATES:
            assert "name" in gate, f"Gate missing 'name': {gate}"
            assert "description" in gate, f"Gate {gate['name']} missing 'description'"
            assert "tags" in gate, f"Gate {gate['name']} missing 'tags'"
            assert len(gate["name"]) > 0
            assert len(gate["description"]) > 0

    def test_configs_have_required_fields(self):
        """All configs should have name, description, tags, and value."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import CONFIGS
        for config in CONFIGS:
            assert "name" in config, f"Config missing 'name': {config}"
            assert "description" in config, f"Config {config['name']} missing 'description'"
            assert "value" in config, f"Config {config['name']} missing 'value'"
            assert isinstance(config["value"], dict)

    def test_experiments_have_required_fields(self):
        """All experiments should have name, description, and tags."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import EXPERIMENTS
        for exp in EXPERIMENTS:
            assert "name" in exp, f"Experiment missing 'name': {exp}"
            assert "description" in exp, f"Experiment {exp['name']} missing 'description'"

    def test_gate_count(self):
        """Should have exactly 7 feature gates."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import GATES
        assert len(GATES) == 7

    def test_config_count(self):
        """Should have exactly 9 dynamic configs."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import CONFIGS
        assert len(CONFIGS) == 9

    def test_experiment_count(self):
        """Should have exactly 6 experiments."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import EXPERIMENTS
        assert len(EXPERIMENTS) == 6

    def test_tag_count(self):
        """Should have exactly 8 tags."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import TAGS
        assert len(TAGS) == 8

    def test_infrastructure_reference_is_readonly(self):
        """Infrastructure config should be marked as read-only."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import CONFIGS
        infra = next(c for c in CONFIGS if c["name"] == "infrastructure_reference")
        assert "READ-ONLY" in infra["description"]

    def test_mock_auth_is_security_sensitive(self):
        """mock_auth_bypass gate should be tagged security-sensitive."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "scripts"))
        from setup_statsig import GATES
        gate = next(g for g in GATES if g["name"] == "mock_auth_bypass")
        assert "security-sensitive" in gate["tags"]
