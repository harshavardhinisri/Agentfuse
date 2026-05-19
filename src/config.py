"""Configuration management for AgentFuse."""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class Settings(BaseSettings):
    """Main application settings."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "postgresql://agentfuse:agentfuse@localhost:5432/agentfuse"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Classifier
    classifier_model_path: str = "models/deberta-classifier"
    classifier_batch_size: int = 32
    classifier_device: str = "cpu"  # "cpu" or "cuda"
    classifier_cache_size: int = 1000

    # Policy
    policy_config_path: str = "config/policies.yaml"
    max_action_history: int = 5

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"

    # MCP
    mcp_timeout_seconds: int = 30
    mcp_max_concurrent: int = 10

    # Admin
    admin_secret_key: str = "dev-secret-key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


class PolicyConfig:
    """Load and manage policy configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize policy config.

        Args:
            config_path: Path to policies.yaml. Uses default if None.
        """
        if config_path is None:
            config_path = get_settings().policy_config_path

        self.config_path = config_path
        self.policies = self._load_config()

    def _load_config(self) -> dict:
        """Load policies from YAML file."""
        if not os.path.exists(self.config_path):
            return self._default_policies()

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f) or {}

        return config

    def _default_policies(self) -> dict:
        """Return default policies if config file doesn't exist."""
        return {
            "agents": {
                "default": {
                    "scope": "staging",
                    "max_parallel_actions": 10,
                    "require_approval_on_yellow": False,
                    "require_approval_on_red": True,
                }
            },
            "rules": {
                "prod_prefix": ["prod_", "production_", "prod-"],
                "config_files": [
                    "/etc/",
                    "config.yaml",
                    "settings.json",
                    ".env",
                ],
                "dangerous_commands": [
                    "rm -rf",
                    "dd if=",
                    "mkfs",
                    ":(){ :|:& };:",  # fork bomb
                ],
            },
        }

    def get_agent_config(self, agent_id: str) -> dict:
        """Get configuration for a specific agent."""
        agents = self.policies.get("agents", {})
        return agents.get(agent_id, agents.get("default", {}))

    def is_prod_scope(self, scope: str) -> bool:
        """Check if a scope is production."""
        prod_prefixes = self.policies.get("rules", {}).get("prod_prefix", [])
        return any(scope.startswith(prefix) for prefix in prod_prefixes)

    def is_config_file(self, path: str) -> bool:
        """Check if a path is a config/sensitive file."""
        config_files = self.policies.get("rules", {}).get("config_files", [])
        return any(
            config_pattern in path
            for config_pattern in config_files
        )

    def is_dangerous_command(self, command: str) -> bool:
        """Check if a command is in the dangerous list."""
        dangerous = self.policies.get("rules", {}).get("dangerous_commands", [])
        return any(
            danger in command.lower()
            for danger in dangerous
        )

    def reload(self) -> None:
        """Reload policies from file."""
        self.policies = self._load_config()


# Global policy config instance
_policy_config: Optional[PolicyConfig] = None


def get_policy_config() -> PolicyConfig:
    """Get global policy config instance."""
    global _policy_config
    if _policy_config is None:
        _policy_config = PolicyConfig()
    return _policy_config
