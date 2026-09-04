"""Composio + Google Places tool executors for the Gisto desktop app.

Provides ``run_tool()`` — the single entry point the Solar-reply thread calls
when the model emits a ``__TOOL__<type>=<payload>`` marker.

Recognized tool types:
- ``places_find_place=<query>`` — Google Places text search + details
  (uses the embedded Google Places key).
- ``composio_action=<app>:<action>:<json-params>`` — an arbitrary Composio
  action (uses the embedded Composio key, read + write enabled on all tools).
- ``composio_list_connections`` — list all the user's Composio connections
  (the "Connections" panel in settings reads from this too).

No key is exposed to the user; keys come from ``src.desktop.keys``.

To add more tools later, add another ``if tool_type == ...:`` branch here
and teach the Solar system prompt about the new marker syntax.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Optional

from src.desktop.keys import (
    google_places_api_key,
    google_places_base_url,
    composio_api_key,
    composio_base_url,
)


# ---------------------------------------------------------------------------
# Google Places
# ---------------------------------------------------------------------------

_GOOGLE_API_KEY = google_places_api_key()
_GOOGLE_BASE = google_places_base_url()


def places_text_search(query: str) -> dict[str, Any]:
    """Text search for places matching *query*."""
    if not _GOOGLE_API_KEY:
        return {"status": "error", "error": "Google Places key not configured"}

    params: dict[str, str] = {
        "query": query,
        "key": _GOOGLE_API_KEY,
        "language": "en",
        "type": "textquery",
        "fields": (
            "place_id,name,formatted_address,geometry,"
            "formatted_phone_number,rating,reviews,website,types"
        ),
    }
    url = f"{_GOOGLE_BASE}/textsearch/json?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Gisto Desktop/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return {"status": data.get("status", "UNKNOWN"), "results": data.get("results", [])}
    except Exception as e:
        return {"status": "error", "error": f"Places search failed: {e}"}


def places_details(place_id: str) -> dict[str, Any]:
    """Fetch detailed info for *place_id*."""
    if not _GOOGLE_API_KEY:
        return {"status": "error", "error": "Google Places key not configured"}

    params: dict[str, str] = {
        "place_id": place_id,
        "key": _GOOGLE_API_KEY,
        "language": "en",
        "fields": (
            "name,formatted_address,geometry,"
            "formatted_phone_number,rating,reviews,website,types"
        ),
    }
    url = f"{_GOOGLE_BASE}/details/json?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Gisto Desktop/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return {"status": data.get("status", "UNKNOWN"), "result": data.get("result", {})}
    except Exception as e:
        return {"status": "error", "error": f"Place details failed: {e}"}


def places_find_place(query: str) -> str:
    """Search for *query*, grab details of the top result, return a human
    summary string that can be fed back to Solar as a second-turn message.
    """
    search = places_text_search(query)
    if search.get("status") != "OK" or not search.get("results"):
        err = search.get("error", "No results found")
        return f"[places search error]: {err}"

    top = search["results"][0]
    pid = top.get("place_id") or top.get("id")
    details = places_details(pid) if pid else {}
    place = details.get("result", {})
    if not place:
        place = top

    name = place.get("name") or "Unknown"
    address = place.get("formatted_address") or ""
    phone = place.get("formatted_phone_number") or ""
    rating = place.get("rating")
    reviews = place.get("reviews") or []
    types = place.get("types") or []
    website = place.get("website") or ""
    geometry = place.get("geometry") or {}
    loc = geometry.get("location", {}) if geometry else {}

    lines = [f"Here's what I found for '{query}':\n"]
    lines.append(f"{name}")
    if address:
        lines.append(f"Address: {address}")
    if phone:
        lines.append(f"Phone: {phone}")
    if rating:
        lines.append(f"Rating: {rating} / 5")
    if website:
        lines.append(f"Website: {website}")
    if loc:
        lines.append(f"Location: {loc.get('lat')}, {loc.get('lng')}")
    if reviews:
        lines.append("\nTop reviews:")
        for rv in reviews[:2]:
            txt = rv.get("text", {}).get("text", "No text") if isinstance(rv.get("text"), dict) else str(rv.get("text", ""))
            author = rv.get("author_name", "someone")
            lines.append(f"- {author}: {txt}")
    if types:
        lines.append(f"\nTypes: {', '.join(types)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Composio
# ---------------------------------------------------------------------------

_COMPOSIO_KEY = composio_api_key()
_COMPOSIO_BASE = composio_base_url()
_COMPOSIO_UNAVAILABLE = not _COMPOSIO_KEY


def composio_list_connections() -> dict[str, Any]:
    """List all of the user's Composio connections.

    Returns ``{"status": "ok", "connections": [...]}`` or an error dict.
    Each connection dict includes ``id``, ``app_name``, ``app_title``,
    ``app_icon``, ``connected_at``, and other metadata Composio returns.
    """
    if _COMPOSIO_UNAVAILABLE:
        return {"status": "error", "error": "Composio key not configured"}

    url = f"{_COMPOSIO_BASE}/connections"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {_COMPOSIO_KEY}",
                "User-Agent": "Gisto Desktop/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        # Normalize response shape: Composio may wrap in "data" or return a list.
        conns = data.get("connections") or data.get("data") or data.get("results") or []
        if isinstance(conns, dict):
            conns = list(conns.values()) if conns else []
        return {"status": "ok", "connections": conns}
    except Exception as e:
        return {"status": "error", "error": f"Composio connections list failed: {e}"}


def composio_execute(app_name: str, action_name: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Execute a single Composio action on *app_name*.

    Returns ``{"status": "ok", "data": ..."}`` or an error dict.
    """
    if _COMPOSIO_UNAVAILABLE:
        return {"status": "error", "error": "Composio key not configured"}

    body = json.dumps({
        "app": app_name,
        "action": action_name,
        "params": params or {},
    }).encode()

    url = f"{_COMPOSIO_BASE}/actions/execute"
    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {_COMPOSIO_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "Gisto Desktop/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return {"status": "ok", "data": data}
    except Exception as e:
        return {"status": "error", "error": f"Composio call failed: {e}"}


# ---------------------------------------------------------------------------
# Tool dispatcher — the single entry point the reply thread uses.
# ---------------------------------------------------------------------------


def run_tool(tool_call: str) -> str:
    """Run a tool described by *tool_call* (a ``__TOOL__<type>=<payload>``
    marker). Returns a plain-text result ready to feed back to Solar.
    """
    if not tool_call.startswith("__TOOL__"):
        return f"[tool call not recognized: {tool_call}]"

    spec = tool_call[len("__TOOL__"):]
    if "=" not in spec:
        return "[tool call malformed: missing '=' payload separator]"

    tool_type, payload = spec.split("=", 1)

    if tool_type == "places_find_place":
        return places_find_place(payload)

    if tool_type == "composio_list_connections":
        result = composio_list_connections()
        if result.get("status") == "ok":
            cons = result.get("connections", [])
            if not cons:
                return "No Composio connections found. Connect an app in the Connections panel (Settings → API & Voice → Connections)."
            lines = [f"Your Composio connections ({len(cons)}):"]
            for c in cons:
                app = c.get("app_name") or c.get("app") or "?"
                title = c.get("app_title") or c.get("title") or app
                icon = c.get("app_icon") or ""
                status = c.get("connected_at") or c.get("status") or "?"
                lines.append(f"- {title} ({app}) — connected {status}" + (f"  {icon}" if icon else ""))
            return "\n".join(lines)
        return f"[Composio connections error]: {result.get('error', '')}"

    if tool_type == "composio_action":
        # payload format: "<app>:<action>:<json-params>"
        parts = payload.split(":", 2)
        if len(parts) < 2:
            return "[composio action malformed: expected <app>:<action>[:params]]"
        app_name = parts[0]
        action_name = parts[1]
        params_str = parts[2] if len(parts) > 2 else "{}"
        try:
            params = json.loads(params_str) if params_str.strip() else {}
        except Exception:
            params = {}
        result = composio_execute(app_name, action_name, params)
        if result.get("status") == "ok":
            return f"[Composio {app_name}.{action_name}]:\n{json.dumps(result.get('data', {}), indent=2)}"
        return f"[Composio {app_name}.{action_name}] error: {result.get('error', '')}"

    return f"[unsupported tool: {tool_type}]"
