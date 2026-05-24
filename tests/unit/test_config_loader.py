import yaml

from council.config.loader import config_snapshot_yaml, redact_config_secrets
from council.config.schema import RunConfig


def test_redact_config_secrets():
    data = {
        "name": "test",
        "openrouter_api_key": "sk-or-secret",
        "openai_api_key": "sk-openai-secret",
        "prompt": "hello",
    }
    redacted = redact_config_secrets(data)

    assert redacted["openrouter_api_key"] == "***REDACTED***"
    assert redacted["openai_api_key"] == "***REDACTED***"
    assert data["openrouter_api_key"] == "sk-or-secret"  # original unchanged


def test_redact_config_secrets_leaves_missing_keys_alone():
    data = {"name": "test", "prompt": "hello"}
    redacted = redact_config_secrets(data)
    assert "openrouter_api_key" not in redacted
    assert "openai_api_key" not in redacted


def test_config_snapshot_yaml_redacts_keys():
    config = RunConfig(
        name="test_run",
        prompt="Should we?",
        openrouter_api_key="sk-or-live-key",
        openai_api_key="sk-openai-live-key",
        agents=[
            {"id": "a", "model": "test/model"},
            {"id": "b", "model": "test/model2"},
        ],
    )
    snapshot = config_snapshot_yaml(config)
    parsed = yaml.safe_load(snapshot)

    assert parsed["openrouter_api_key"] == "***REDACTED***"
    assert parsed["openai_api_key"] == "***REDACTED***"
    assert "sk-or-live-key" not in snapshot
    assert "sk-openai-live-key" not in snapshot
