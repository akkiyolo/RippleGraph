"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration – reads .env automatically."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── HydraDB ──────────────────────────────────────────────
    hydra_db_api_key: str = Field(description="HydraDB API key")
    hydra_db_tenant_id: str = Field(default="hackhydra", description="HydraDB database name")
    hydra_db_sub_tenant_id: str = Field(
        default="demo-user", description="HydraDB collection (user scope)"
    )

    # ── LLM Providers ────────────────────────────────────────
    llm_provider: str = Field(default="gemini", description="Active LLM provider")
    groq_api_key: str = Field(default="", description="Groq API key")
    mistral_api_key: str = Field(default="", description="Mistral API key")
    google_api_key: str = Field(default="", description="Google / Gemini API key")
    cerebras_api_key: str = Field(default="", description="Cerebras API key")

    # ── LangSmith (optional) ─────────────────────────────────
    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com", description="LangSmith endpoint"
    )
    langsmith_api_key: str = Field(default="", description="LangSmith API key")
    langsmith_project: str = Field(default="RippleGraph", description="LangSmith project name")

    # ── Ripple Retrieval ─────────────────────────────────────
    ripple_max_hops: int = Field(default=2, ge=1, le=5, description="Max graph expansion hops")
    ripple_max_nodes: int = Field(
        default=30, ge=5, le=200, description="Max nodes in expansion"
    )
    ripple_hop_decay: float = Field(
        default=0.75, ge=0.1, le=1.0, description="Hop decay factor"
    )

    # ── Abstention ───────────────────────────────────────────
    abstention_threshold: float = Field(
        default=0.50, ge=0.0, le=1.0, description="Confidence threshold for abstention"
    )
    min_evidence_count: int = Field(
        default=2, ge=1, description="Minimum evidence count before answering"
    )

    # ── Application ──────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Logging level")

    # ── Relation Weights (configurable) ──────────────────────
    weight_supersedes: float = 1.00
    weight_contradicts: float = 0.95
    weight_supports: float = 0.90
    weight_derived_from: float = 0.80
    weight_decided_in: float = 0.80
    weight_part_of: float = 0.70
    weight_about: float = 0.60
    weight_related_to: float = 0.45
    weight_mentions: float = 0.25

    # ── Confidence Weights (configurable) ────────────────────
    confidence_corroboration_weight: float = 0.4
    confidence_recency_weight: float = 0.2
    confidence_contradiction_penalty: float = 0.3
    confidence_evidence_weight: float = 0.1

    def get_relation_weight(self, relation_type: str) -> float:
        """Return the weight for a given relation type."""
        weights = {
            "SUPERSEDES": self.weight_supersedes,
            "SUPERSEDED_BY": self.weight_supersedes,
            "CONTRADICTS": self.weight_contradicts,
            "SUPPORTS": self.weight_supports,
            "DERIVED_FROM": self.weight_derived_from,
            "DECIDED_IN": self.weight_decided_in,
            "PART_OF": self.weight_part_of,
            "ABOUT": self.weight_about,
            "RELATED_TO": self.weight_related_to,
            "MENTIONS": self.weight_mentions,
        }
        return weights.get(relation_type.upper(), 0.3)


def get_settings() -> Settings:
    """Singleton-ish factory for Settings."""
    return Settings()
