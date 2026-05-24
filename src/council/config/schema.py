"""Pydantic schemas for run config, experiment batches, and nested settings."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AgentConfig(BaseModel):
    id: str
    model: str
    temperature: float = 0.7
    seed: Optional[int] = None
    timeout: float = 90.0
    provider_pin: Optional[str] = None  # OpenRouter provider routing


class TerminationConfig(BaseModel):
    min_new_claims_per_round: int = 1
    no_challenge_rounds: int = 2
    min_position_update_rate: float = 0.1
    max_rounds: int = 10


class IdentityConfig(BaseModel):
    similarity_high: float = 0.9   # auto-merge above this
    similarity_low: float = 0.7    # new claim below this
    disambiguation_model: str = "anthropic/claude-haiku-4-5-20251001"


class EmbedderConfig(BaseModel):
    provider: Literal["openai", "openrouter", "local", "none"] = "local"
    model: str = "all-MiniLM-L6-v2"


class ManipulationConfig(BaseModel):
    injection_n: int = 3                  # top-N claims to disguise per agent
    inject_every_n_rounds: int = 1        # how often to inject new disguised content
    disguise_model: str = "anthropic/claude-haiku-4-5-20251001"


class RateLimitsConfig(BaseModel):
    stagger_delay: float = 2.0        # seconds between launching parallel agent calls
    max_backoff: float = 120.0        # ceiling for retry backoff (free models can need long waits)
    per_model_concurrency: int = 1    # max simultaneous requests per unique model ID


class RunConfig(BaseModel):
    name: str = "run"
    prompt: Optional[str] = None
    prompt_file: Optional[str] = None
    version: Literal["A", "B"] = "A"
    mock: bool = False

    agents: list[AgentConfig] = Field(default_factory=list)

    arbiter_model: str = "anthropic/claude-sonnet-4-6"
    arbiter_temperature: float = 0.2
    arbiter_seed: Optional[int] = None

    observer_model: str = "anthropic/claude-haiku-4-5-20251001"
    observer_temperature: float = 0.2
    observer_frequency: int = 1  # run observer every N rounds

    termination: TerminationConfig = Field(default_factory=TerminationConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    manipulation: ManipulationConfig = Field(default_factory=ManipulationConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)

    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None  # for embeddings when provider=openai
    artifacts_dir: str = "runs"

    @field_validator("agents")
    @classmethod
    def at_least_two_agents(cls, v: list) -> list:
        if len(v) < 1:
            raise ValueError("At least 1 agent must be configured")
        return v

    def get_prompt_text(self) -> str:
        if self.prompt:
            return self.prompt
        if self.prompt_file:
            with open(self.prompt_file) as f:
                return f.read().strip()
        raise ValueError("Either 'prompt' or 'prompt_file' must be set")


class ExperimentEntry(BaseModel):
    name: str
    version: Literal["A", "B"] = "A"
    roster: list[str] = Field(default_factory=list)
    prompt_file: Optional[str] = None
    prompt: Optional[str] = None
    overrides: dict = Field(default_factory=dict)


class ExperimentConfig(BaseModel):
    experiments: list[ExperimentEntry]
    base: dict = Field(default_factory=dict)  # shared config applied to all runs
