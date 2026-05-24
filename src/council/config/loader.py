"""YAML config loading and environment variable resolution for API keys."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

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
    data = config.model_dump()
    # Redact API keys from snapshot
    data["openrouter_api_key"] = "***REDACTED***" if data.get("openrouter_api_key") else None
    data["openai_api_key"] = "***REDACTED***" if data.get("openai_api_key") else None
    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
