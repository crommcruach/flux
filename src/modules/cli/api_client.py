"""
Thin HTTP client for the Flux local REST API.

All CLI commands go through here so the CLI stays a clean HTTP client.
The backend is always localhost — latency is <1 ms, no auth needed.
"""
import os
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, Optional

from .errors import CLIError

# Allow override via env for testing
_DEFAULT_BASE = 'http://localhost:5000'


def _base_url() -> str:
    return os.getenv('FLUX_API_URL', _DEFAULT_BASE).rstrip('/')


def api_call(
    method: str,
    path: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """
    Make an HTTP call to the Flux backend.

    Args:
        method:  HTTP verb ('GET', 'POST', 'PUT', 'DELETE').
        path:    URL path, e.g. '/api/player/video/play'.
        data:    Optional JSON body (for POST/PUT).
        params:  Optional query-string parameters (for GET).
        timeout: Seconds before giving up.

    Returns:
        Parsed JSON response dict.

    Raises:
        CLIError: On connection failure, HTTP error, or non-JSON response.
    """
    url = _base_url() + path
    if params:
        url += '?' + urllib.parse.urlencode(params)

    body: Optional[bytes] = None
    headers: Dict[str, str] = {}
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if hasattr(exc, 'reason') else str(exc)
        raise CLIError(
            f"Cannot connect to Flux backend ({_base_url()})",
            "Start the backend with:  python src/main.py",
            examples=['# python src/main.py'],
        ) from exc
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode('utf-8')
            err_json = json.loads(body_text)
            msg = err_json.get('error') or err_json.get('message') or body_text
        except Exception:
            msg = str(exc)
        raise CLIError(f"API error {exc.code}: {msg}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CLIError(f"Unexpected non-JSON response from API: {raw[:200]}") from exc
