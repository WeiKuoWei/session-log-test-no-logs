import tomllib
from pathlib import Path

DEFAULTS = {
    "provider": "anthropic",
    "model": "claude-sonnet-5-5",
    "max_tokens": 2048,
    "timeout_seconds": 60,
    "workers": 4,
    "max_attempts": 4,
    "backoff_seconds": 2.0,
    "api_base": "https://api.anthropic.com",
    "anthropic_version": "2023-06-01",
    "input_dir": "materials/requests",
    "state_root": "state",
    "policy_version": "northstar-intake-policy-2026-10-26",
}
API_KEY_ENV = "ANTHROPIC_API_KEY"


def load_config(path="intake.toml", **overrides):
    config = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        config.update(tomllib.loads(p.read_text(encoding="utf-8")))
    config.update({k: v for k, v in overrides.items() if v is not None})
    return config


def state_dir(config):
    return Path(config["state_root"]) / config["provider"]


def extraction_settings(config):
    """The settings that change what the model produces. Hashed into the fingerprint."""
    keys = ["provider", "model", "max_tokens", "temperature", "anthropic_version"]
    return {k: config.get(k) for k in keys}
