from __future__ import annotations
"""Statsig SDK wrapper with graceful fallback.

Provides helpers for feature gates, dynamic configs, and experiments.
If Statsig is unreachable or not configured, all methods return hardcoded
defaults so the app continues working without Statsig.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Module-level state — populated by initialize()
_initialized = False


def initialize() -> bool:
    """Initialize Statsig SDK. Call once at Lambda cold start.

    Returns True if SDK initialized successfully, False on fallback.
    """
    global _initialized
    server_key = os.environ.get("STATSIG_SERVER_KEY", "")
    if not server_key:
        logger.info("STATSIG_SERVER_KEY not set — using hardcoded defaults")
        return False
    try:
        from statsig import statsig as statsig_module
        from statsig import StatsigOptions

        tier = os.environ.get("APP_ENV", "development")
        statsig_module.initialize(
            server_key,
            StatsigOptions(tier=tier),
        )
        _initialized = True
        logger.info("Statsig initialized (tier=%s)", tier)
        return True
    except Exception:
        logger.warning("Statsig init failed — using hardcoded defaults", exc_info=True)
        return False


def shutdown() -> None:
    """Flush + shutdown Statsig SDK. Call on Lambda freeze."""
    global _initialized
    if not _initialized:
        return
    try:
        from statsig import statsig as statsig_module
        statsig_module.shutdown()
        _initialized = False
    except Exception:
        logger.warning("Statsig shutdown error", exc_info=True)


# ──────────────────────────────────────────────
# Feature Gates
# ──────────────────────────────────────────────

# Hardcoded defaults — used when Statsig is unreachable
_GATE_DEFAULTS: dict[str, bool] = {
    "demo_mode": False,
    "force_demo_mode": False,
    "mock_auth_bypass": False,
    "api_docs_enabled": False,
    "dd_trace_enabled": True,
    "dd_capture_payload": False,
    "dd_serverless_logs": True,
}


def check_gate(gate_name: str) -> bool:
    """Check if a feature gate is enabled. Returns default if Statsig is down."""
    default = _GATE_DEFAULTS.get(gate_name, False)
    if not _initialized:
        return default
    try:
        from statsig import statsig as statsig_module
        from statsig import StatsigUser
        # Server-side gates use a dummy user (gates apply globally per-env)
        return statsig_module.check_gate(StatsigUser(user_id="server"), gate_name)
    except Exception:
        logger.warning("Statsig check_gate(%s) failed, returning default=%s", gate_name, default)
        return default


# ──────────────────────────────────────────────
# Dynamic Configs
# ──────────────────────────────────────────────

# Hardcoded defaults — used when Statsig is unreachable
_CONFIG_DEFAULTS: dict[str, dict] = {
    "ai_models": {
        "haiku_model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "sonnet_model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "default_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "max_tokens": 4096,
        "temperature": 0.3,
        "max_content_chars": 50000,
        "max_chunks_per_run": 10,
        "bedrock_read_timeout": 300,
        "bedrock_max_retries": 2,
    },
    "pagination": {
        "regulations_page_size": 20,
        "gaps_page_size": 20,
        "reports_page_size": 10,
        "communications_page_size": 20,
        "notifications_page_size": 20,
    },
    "scraper": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 PaceCareOnline/1.0"
        ),
    },
    "ingestion": {
        "relevance_threshold": 0.3,
    },
    "database": {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 300,
    },
    "dashboard": {
        "relevance_threshold": 0.5,
        "deadlines_window_days": 90,
        "deadlines_limit": 10,
        "stale_run_cleanup_minutes": 10,
    },
    "datadog": {
        "trace_sample_rate": 0.1,
        "trace_ignore_resources": "/health",
        "rum_session_sample_rate": 100,
        "rum_replay_sample_rate": 20,
        "rum_privacy_level": "mask-user-input",
    },
}


def get_config(config_name: str, param: str | None = None, default=None):
    """Get a dynamic config value.

    Args:
        config_name: Name of the config group (e.g., "ai_models")
        param: Optional specific parameter name within the config
        default: Override default (falls back to _CONFIG_DEFAULTS)

    Returns:
        The config dict if param is None, or the specific parameter value.
    """
    config_defaults = _CONFIG_DEFAULTS.get(config_name, {})

    if not _initialized:
        if param is None:
            return config_defaults
        return config_defaults.get(param, default)

    try:
        from statsig import statsig as statsig_module
        from statsig import StatsigUser
        config = statsig_module.get_config(StatsigUser(user_id="server"), config_name)
        if param is None:
            # Merge Statsig values over defaults
            merged = {**config_defaults, **config.value}
            return merged
        return config.get(param, config_defaults.get(param, default))
    except Exception:
        logger.warning("Statsig get_config(%s) failed, returning defaults", config_name)
        if param is None:
            return config_defaults
        return config_defaults.get(param, default)


# ──────────────────────────────────────────────
# Experiments
# ──────────────────────────────────────────────

_EXPERIMENT_DEFAULTS: dict[str, dict] = {
    "llm_temperature": {"temperature": 0.3},
    "relevance_threshold": {"threshold": 0.3},
    "regulation_page_size": {"page_size": 20},
    "gap_page_size": {"page_size": 20},
    "report_page_size": {"page_size": 10},
    "dashboard_relevance": {"threshold": 0.5},
}


def get_experiment(experiment_name: str, param: str, default=None):
    """Get an experiment parameter value.

    Args:
        experiment_name: Name of the Statsig experiment
        param: Parameter name within the experiment
        default: Override default (falls back to _EXPERIMENT_DEFAULTS)
    """
    exp_defaults = _EXPERIMENT_DEFAULTS.get(experiment_name, {})
    fallback = exp_defaults.get(param, default)

    if not _initialized:
        return fallback

    try:
        from statsig import statsig as statsig_module
        from statsig import StatsigUser
        experiment = statsig_module.get_experiment(
            StatsigUser(user_id="server"), experiment_name
        )
        return experiment.get(param, fallback)
    except Exception:
        logger.warning("Statsig get_experiment(%s) failed, returning default", experiment_name)
        return fallback
