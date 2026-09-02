"""Gisto configuration system.

Loads and validates config.yaml. No secrets are hardcoded anywhere in this
framework — every key, token, and credential comes from the user's config at
runtime, and missing required fields produce clear errors.

Usage::

    from src.config import get_config, is_integration_enabled, get_integration_config

    cfg = get_config()
    if is_integration_enabled("discord"):
        token = cfg["integrations"]["discord"]["bot_token"]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# ============================================================================
# Where to look for config.yaml
# ============================================================================

# By default we look for config.yaml next to this file's parent package root.
# The user can override by setting the GISTO_CONFIG environment variable.
_DEFAULT_CONFIG_NAMES = ["config.yaml", "config.yml"]


def _find_config_path() -> Path:
    """Locate the user's config.yaml.

    Checks, in order:
    1. GISTO_CONFIG environment variable (explicit path)
    2. config.yaml alongside the package root
    3. config.yaml in the current working directory

    Returns the first existing, readable path.
    """
    env_path = os.environ.get("GISTO_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p
        raise ConfigError(f"GISTO_CONFIG points to non-existent file: {p}")

    # Walk up from this file to find a config.yaml sitting at the repo root.
    root = Path(__file__).resolve().parent.parent
    for candidate_name in _DEFAULT_CONFIG_NAMES:
        candidate = root / candidate_name
        if candidate.exists():
            return candidate

    # Fall back to cwd.
    for candidate_name in _DEFAULT_CONFIG_NAMES:
        candidate = Path.cwd() / candidate_name
        if candidate.exists():
            return candidate

    names = ", ".join(_DEFAULT_CONFIG_NAMES)
    raise ConfigError(
        f"No config file found. Looked for {names} in:\n"
        f"  - {root}\n"
        f"  - {Path.cwd()}\n"
        f"Set GISTO_CONFIG to the path of your config.yaml, or place one of "
        f"those names alongside the package root or in the current directory."
    )


# ============================================================================
# Config container
# ============================================================================

class Config:
    """Immutable view of the loaded configuration."""

    def __init__(self, data: Dict[str, Any], path: Path) -> None:
        self._data = data
        self._path = path

    @property
    def raw(self) -> Dict[str, Any]:
        """The full configuration dictionary."""
        return dict(self._data)

    @property
    def path(self) -> Path:
        """Path to the config file that was loaded."""
        return self._path

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-path access, e.g. ``get("integrations.discord.bot_token")``."""
        current: Any = self._data
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"Config(path={self._path!s}, keys={sorted(self._data.keys())!r})"


# ============================================================================
# Validation
# ============================================================================

class ConfigError(Exception):
    """Raised when config is missing, unreadable, or invalid."""


def _validate_config(data: Dict[str, Any]) -> None:
    """Validate the loaded config dictionary.

    Raises ConfigError with actionable messages when something required is
    missing or malformed.
    """
    if not isinstance(data, dict):
        raise ConfigError("config.yaml must contain a YAML mapping at the top level.")

    gisto = data.get("gisto")
    if not isinstance(gisto, dict):
        raise ConfigError(
            "config.yaml must contain a 'gisto' section. "
            "Copy config.example.yaml and fill it in."
        )

    # --- memory_dir ---
    memory_dir = gisto.get("memory_dir")
    if not memory_dir or not isinstance(memory_dir, str):
        raise ConfigError(
            "gisto.memory_dir is required. Set it to a directory where Gisto "
            "should store per-user memory (e.g. ./data/memory)."
        )

    # --- modules ---
    modules = gisto.get("modules")
    if not isinstance(modules, dict):
        raise ConfigError(
            "gisto.modules must be a mapping of module name -> enabled flag. "
            "Copy config.example.yaml and fill it in."
        )
    known_modules = {"personal", "agency"}
    for key in modules:
        if key not in known_modules:
            raise ConfigError(
                f"Unknown module in gisto.modules: {key!r}. "
                f"Known modules: {sorted(known_modules)}."
            )

    # --- integrations ---
    integrations = data.get("integrations")
    if not isinstance(integrations, dict):
        raise ConfigError(
            "config.yaml must contain an 'integrations' section. "
            "Copy config.example.yaml and fill it in."
        )

    known_integrations = {"discord", "slack", "google", "composio"}
    for name, block in integrations.items():
        if name not in known_integrations:
            raise ConfigError(
                f"Unknown integration: {name!r}. "
                f"Known integrations: {sorted(known_integrations)}."
            )
        if not isinstance(block, dict):
            raise ConfigError(
                f"Integration {name!r} must be a mapping with an 'enabled' flag "
                f"and its own config fields. Copy config.example.yaml and fill it in."
            )
        enabled = block.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ConfigError(
                f"Integration {name!r}: 'enabled' must be true or false."
            )
        if enabled:
            _validate_integration_config(name, block)

    # --- limits (optional, but validate if present) ---
    limits = gisto.get("limits")
    if limits is not None and not isinstance(limits, dict):
        raise ConfigError("gisto.limits must be a mapping if present.")


def _validate_integration_config(name: str, block: Dict[str, Any]) -> None:
    """Validate an enabled integration's config.

    Each integration defines its own required fields. We validate the common
    shape here and let each integration add its own checks.
    """
    # Every integration block should at least have an 'enabled' flag (already
    # checked above) and whatever fields that integration needs. We do a light
    # generic check: if the block has a token-like field named bot_token,
    # client_secret, api_key, etc. and enabled is true, warn if it's still a
    # placeholder.
    tokenish_keys = {
        "bot_token",
        "client_secret",
        "client_id",
        "signing_secret",
        "api_key",
        "secret",
    }
    for key in tokenish_keys:
        value = block.get(key)
        if value is not None and isinstance(value, str) and _looks_like_placeholder(value):
            # Don't hard-fail on placeholders — the integration will fail at
            # runtime with a clear message. But help the user notice.
            import warnings

            warnings.warn(
                f"{name!r} is enabled but {key!r} looks like a placeholder "
                f"('{value}'). Replace it with a real value in config.yaml.",
                stacklevel=2,
            )


def _looks_like_placeholder(value: str) -> bool:
    """Return True if a string looks like an unfilled template placeholder."""
    lowered = value.strip().lower()
    return (
        lowered in {"", "your_token_here", "your_api_key_here", "your_client_id_here"}
        or lowered.startswith("your_")
        or lowered.startswith("<")
        or lowered.endswith(">")
        or len(value.strip()) <= 2
    )


# ============================================================================
# Public API
# ============================================================================

_CONFIG: Optional[Config] = None
"""Lazily-loaded singleton config instance."""


def load_config(path: Optional[Path] = None) -> Config:
    """Load and validate the config, returning a Config instance.

    Called automatically by ``get_config()`` on first use. You can call it
    directly if you want to control the path or re-load after a change.
    """
    global _CONFIG
    if path is None:
        path = _find_config_path()
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"config.yaml is not valid YAML: {path}\n{exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read config.yaml: {path}\n{exc}") from exc

    _validate_config(data)
    _CONFIG = Config(data, path)
    return _CONFIG


def get_config() -> Config:
    """Return the loaded config, loading it on first call."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG


def reset_config() -> None:
    """Clear the cached config. Mostly useful in tests."""
    global _CONFIG
    _CONFIG = None


def is_module_enabled(module_name: str) -> bool:
    """Return True if the given module is enabled in config."""
    cfg = get_config()
    enabled = cfg.get(f"gisto.modules.{module_name}", False)
    return bool(enabled)


def is_integration_enabled(integration_name: str) -> bool:
    """Return True if the given integration is enabled in config."""
    cfg = get_config()
    enabled = cfg.get(f"integrations.{integration_name}.enabled", False)
    return bool(enabled)


def get_integration_config(integration_name: str) -> Dict[str, Any]:
    """Return the config block for an integration, raising if missing."""
    cfg = get_config()
    block = cfg.get(f"integrations.{integration_name}")
    if not isinstance(block, dict):
        raise ConfigError(
            f"Integration {integration_name!r} is not configured. "
            f"Copy config.example.yaml and fill in the {integration_name} section."
        )
    return dict(block)


def get_gisto_config() -> Dict[str, Any]:
    """Return the 'gisto' section of config."""
    cfg = get_config()
    gisto = cfg.get("gisto")
    if not isinstance(gisto, dict):
        raise ConfigError("config.yaml 'gisto' section is missing or invalid.")
    return dict(gisto)


# ============================================================================
# CLI helper
# ============================================================================

def print_config_summary() -> None:
    """Print a safe, non-secret summary of the current config for debugging."""
    cfg = get_config()
    print("Gisto config loaded from:", cfg.path)
    print("gisto.name:", cfg.get("gisto.name", "<not set>"))
    print("gisto.memory_dir:", cfg.get("gisto.memory_dir", "<not set>"))
    print("gisto.onboarding_enabled:", cfg.get("gisto.onboarding_enabled", "<not set>"))
    print("modules:")
    for key in ("personal", "agency"):
        print(f"  {key}: {is_module_enabled(key)}")
    print("integrations:")
    for name in ("discord", "slack", "google", "composio"):
        enabled = is_integration_enabled(name)
        print(f"  {name}: {'enabled' if enabled else 'disabled'}")
