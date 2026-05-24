"""YAML config loading and environment variable resolution for API keys."""
from __future__ import annotations

import io
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from .schema import RunConfig, ExperimentConfig


def _load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _resolve_env_keys(data: dict) -> dict:
    """Pull API keys from environment if not set in config."""
    if not data.get("openrouter_api_key"):
        data["openrouter_api_key"] = os.environ.get("OPENROUTER_API_KEY")
    if not data.get("openai_api_key"):
        data["openai_api_key"] = os.environ.get("OPENAI_API_KEY")
    return data


def redact_config_secrets(data: dict) -> dict:
    """Return a copy of config data with API keys redacted for safe persistence."""
    redacted = dict(data)
    if redacted.get("openrouter_api_key"):
        redacted["openrouter_api_key"] = "***REDACTED***"
    if redacted.get("openai_api_key"):
        redacted["openai_api_key"] = "***REDACTED***"
    return redacted


def config_snapshot_yaml(config: RunConfig) -> str:
    """Serialize run config to YAML with API keys redacted."""
    buf = io.StringIO()
    yaml.dump(
        redact_config_secrets(config.model_dump()),
        buf,
        default_flow_style=False,
        sort_keys=False,
    )
    return buf.getvalue()


def load_run_config(path: str | Path) -> RunConfig:
    data = _load_yaml(path)
    data = _resolve_env_keys(data)
    try:
        return RunConfig.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Config validation failed in {path}:\n{e}") from e


def load_run_config_from_dict(data: dict) -> RunConfig:
    data = _resolve_env_keys(dict(data))
    try:
        return RunConfig.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Config validation failed:\n{e}") from e


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    data = _load_yaml(path)
    try:
        return ExperimentConfig.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Experiment config validation failed:\n{e}") from e


def snapshot_config(config: RunConfig, output_path: str | Path) -> None:
    """Write the effective config as YAML to the artifact directory."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(config_snapshot_yaml(config))
