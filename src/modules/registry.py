"""Module system base classes and registry for Gisto.

Capabilities are organized as modules that can be toggled on/off from config.
The registry resolves which modules are active and asks them, in order, whether
they can handle a request.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import is_module_enabled


# ---------------------------------------------------------------------------
# Module interface
# ---------------------------------------------------------------------------

class Module:
    """Base class for a Gisto capability module.

    A module is a self-contained capability that the orchestrator can ask
    whether it applies to a request, and then ask to handle the request.
    """

    name: str = ""
    description: str = ""
    summary: str = ""

    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Return True if this module thinks it should handle *user_input*."""
        raise NotImplementedError

    def handle(
        self,
        user_input: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle a request the module has claimed.

        Returns a dict with at least:
        - ``answer``: text the orchestrator can use in its reply
        - ``memory_actions``: list of (``content``, ``kind``) tuples to store
        - ``module``: the module name (set by the orchestrator if missing)
        """
        raise NotImplementedError

    def help(self) -> str:
        """One or two lines describing what this module does."""
        return self.summary or self.description


# ---------------------------------------------------------------------------
# Module registry
# ---------------------------------------------------------------------------

class ModuleRegistry:
    """Resolves which modules are active and provides the orchestrator a way
    to ask them, in priority order, to handle a request.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, Module] = {}
        self._order: List[str] = []

    def register(self, module: Module, *, before: Optional[str] = None) -> None:
        """Register a module.

        By default, registered modules go last (so personal as the fallback
        stays the fallback). Use *before* to insert before a named module.
        """
        name = module.name
        if not name:
            raise ValueError("Module must have a non-empty name")
        if name in self._modules:
            raise ValueError(f"Module already registered: {name!r}")
        self._modules[name] = module
        if before is None:
            self._order.append(name)
        else:
            if before not in self._modules:
                raise ValueError(f"Cannot insert before unknown module: {before!r}")
            idx = self._order.index(before)
            self._order.insert(idx, name)

    def enabled_modules(self) -> List[Module]:
        """Return the enabled modules in priority order."""
        result: List[Module] = []
        for name in self._order:
            if name not in self._modules:
                continue
            if is_module_enabled(name):
                result.append(self._modules[name])
        return result

    def all_registered(self) -> List[Module]:
        """Return all registered modules, in priority order, regardless of config."""
        return [self._modules[name] for name in self._order if name in self._modules]

    def find_handler(
        self, user_input: str, context: Dict[str, Any]
    ) -> Optional[Module]:
        """Return the first enabled module that can handle *user_input*, or None."""
        for module in self.enabled_modules():
            try:
                if module.can_handle(user_input, context):
                    return module
            except Exception:
                # A module that throws in can_handle is not claiming this input.
                continue
        return None

    def list_enabled_help(self) -> str:
        """Return a short help summary of the enabled modules."""
        mods = self.enabled_modules()
        if not mods:
            return "No modules enabled."
        lines = [f"Enabled modules ({len(mods)}):"]
        for m in mods:
            lines.append(f"  - {m.name}: {m.help()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default registry setup
# ---------------------------------------------------------------------------

_default_registry: Optional[ModuleRegistry] = None


def get_default_registry() -> ModuleRegistry:
    """Return the default module registry with the standard modules registered."""
    global _default_registry
    if _default_registry is not None:
        return _default_registry

    from src.modules.personal import PersonalModule
    from src.modules.agency import AgencyModule

    reg = ModuleRegistry()
    # Register agency first; personal last as the fallback.
    reg.register(AgencyModule(), before="personal")
    reg.register(PersonalModule())
    _default_registry = reg
    return _default_registry
