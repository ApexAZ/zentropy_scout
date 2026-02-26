"""Convert ZAP Traditional JSON report to SARIF 2.1.0 for GitHub Security tab.

Usage: python zap-to-sarif.py <input.json> <output.sarif>

ZAP's API scan produces a Traditional JSON report but not SARIF. This script
bridges the gap so DAST findings appear alongside Trivy results in the GitHub
Security tab (private, unlike GitHub Issues).

All findings are uploaded unfiltered. Informational alerts (e.g. 4xx on
invalid IDs) are mapped to SARIF "note" level. Each alert gets a per-result
severity level so GitHub can display accurate severity.

Since DAST results target URLs rather than source files, each location uses
the endpoint path as the artifact URI and startLine=1 as a placeholder.
"""

import hashlib
import json
import re
import sys


def _strip_html(text: str) -> str:
    """Remove HTML tags from ZAP descriptions."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_risk(riskdesc: str) -> str:
    """Extract risk level from ZAP riskdesc 'Risk (Confidence)' format.

    ZAP's riskdesc combines risk and confidence: "Low (High)",
    "Informational (High)", etc. We only care about the risk portion
    (before the parenthesis).

    Args:
        riskdesc: ZAP risk description string.

    Returns:
        Lowercase risk level (e.g. "low", "informational", "medium", "high").

    Examples:
        >>> _parse_risk("Low (High)")
        'low'
        >>> _parse_risk("Informational (High)")
        'informational'
        >>> _parse_risk("Medium (Medium)")
        'medium'
    """
    risk_part = riskdesc.split("(")[0].strip().lower()
    return risk_part or "informational"


def _risk_to_sarif_level(risk: str) -> str:
    """Map ZAP risk level to SARIF severity level.

    SARIF levels: error, warning, note, none.

    Args:
        risk: Lowercase risk string from _parse_risk().

    Returns:
        SARIF severity level string.
    """
    mapping = {
        "high": "error",
        "medium": "warning",
        "low": "warning",
        "informational": "note",
    }
    return mapping.get(risk, "note")


def _make_rule_id(alert: dict) -> str:
    """Generate a unique rule ID from alertRef + alert name.

    ZAP uses the same alertRef (100000) for both "Server Error" and
    "Client Error" alerts. We differentiate them by appending a suffix
    so they get separate SARIF rules with correct names and severities.

    Args:
        alert: ZAP alert dict with "alertRef", "pluginid", and "name" keys.

    Returns:
        Unique rule ID string.
    """
    base_id = str(alert.get("alertRef", alert.get("pluginid", "0")))
    name = alert.get("name", "")

    if base_id == "100000":
        if "Client Error" in name:
            return "100000-client"
        if "Server Error" in name:
            return "100000-server"
        # Fallback: use sanitized name suffix to avoid collisions
        # with known client/server error alerts
        if name:
            suffix = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
            return f"100000-{suffix}"

    return base_id


def _uri_to_path(uri: str) -> str:
    """Strip protocol, host, port, and query string from a URL to get the path.

    Query strings are stripped because SARIF artifact locations must be valid
    file paths.  ZAP attack payloads (e.g. ``php://input``) in query params
    contain ``://`` which GitHub CodeQL rejects.  The full URI including query
    string is preserved in the result ``message.text`` field.
    """
    path = re.sub(r"^\w+://[^/]+(:\d+)?", "", uri) or "/"
    path = path.split("?", 1)[0]
    return path


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
"""Matches a full UUID path segment (e.g. 550e8400-e29b-41d4-a716-446655440000)."""

_LARGE_NUMBER_RE = re.compile(r"^\d{10,}$")
"""Matches numeric-only path segments with 10+ digits (ZAP fuzz payloads).

ZAP replaces UUID path params with large random integers (15-20 digits).
The 10-digit threshold avoids false positives on short numbers like
port numbers, pagination offsets, or version numbers (v1, v2).
"""


def _normalize_path_segment(segment: str) -> str:
    """Replace dynamic path segments with {id} placeholder.

    Normalizes UUIDs and large numeric ZAP fuzz payloads so that the
    same endpoint produces the same artifact URI across scan runs.

    Args:
        segment: A single path segment (between slashes).

    Returns:
        "{id}" if the segment is a UUID or large number, otherwise unchanged.
    """
    if _UUID_RE.match(segment):
        return "{id}"
    if _LARGE_NUMBER_RE.match(segment):
        return "{id}"
    return segment


def _normalize_path(path: str) -> str:
    """Normalize a URL path by replacing dynamic segments with {id}.

    Splits the path on "/", normalizes each segment, and rejoins.

    Args:
        path: URL path (e.g. "/api/v1/personas/8297929860933747743").

    Returns:
        Normalized path (e.g. "/api/v1/personas/{id}").

    Examples:
        >>> _normalize_path("/api/v1/personas/8297929860933747743")
        '/api/v1/personas/{id}'
        >>> _normalize_path("/api/v1/job-variants/variant_id/3811768465121217484")
        '/api/v1/job-variants/variant_id/{id}'
    """
    segments = path.split("/")
    normalized = [_normalize_path_segment(s) for s in segments]
    return "/".join(normalized)


def _compute_fingerprint(rule_id: str, method: str, normalized_path: str) -> str:
    """Compute a stable SARIF fingerprint for a DAST finding.

    GitHub uses partialFingerprints.primaryLocationLineHash to deduplicate
    alerts across scan runs. This function produces a deterministic hash
    from the finding's stable identity: rule + HTTP method + endpoint path.

    Args:
        rule_id: SARIF rule ID (e.g. "10038", "100000-client").
        method: HTTP method (e.g. "GET", "POST").
        normalized_path: URL path with dynamic segments replaced by {id}.

    Returns:
        SHA-256 hex digest (first 16 chars) with ":1" suffix,
        matching GitHub's primaryLocationLineHash format convention.
    """
    identity = f"{rule_id}|{method}|{normalized_path}"
    hash_hex = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return f"{hash_hex}:1"


def convert(zap_json: dict) -> dict:
    """Convert ZAP JSON report to SARIF 2.1.0 format."""
    rules: list[dict] = []
    results: list[dict] = []
    seen_rule_ids: set[str] = set()

    for site in zap_json.get("site", []):
        for alert in site.get("alerts", []):
            rule_id = _make_rule_id(alert)
            risk = _parse_risk(alert.get("riskdesc", ""))
            sarif_level = _risk_to_sarif_level(risk)

            if rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule_id)
                rules.append(
                    {
                        "id": rule_id,
                        "shortDescription": {"text": alert.get("name", "")},
                        "fullDescription": {
                            "text": _strip_html(alert.get("desc", ""))
                        },
                        "helpUri": (
                            f"https://www.zaproxy.org/docs/alerts/"
                            f"{alert.get('pluginid', '0')}/"
                        ),
                        "defaultConfiguration": {"level": sarif_level},
                        "properties": {
                            "tags": [
                                f"external/cwe/cwe-{alert.get('cweid', '0')}"
                            ]
                        },
                    }
                )

            for instance in alert.get("instances", []):
                uri = instance.get("uri", "")
                method = instance.get("method", "GET")
                raw_path = _uri_to_path(uri).lstrip("/") or "api"
                normalized = _normalize_path(raw_path)
                fingerprint = _compute_fingerprint(rule_id, method, normalized)
                results.append(
                    {
                        "ruleId": rule_id,
                        "level": sarif_level,
                        "message": {
                            "text": (
                                f"{alert.get('name', '')} — "
                                f"{method} {uri}"
                            )
                        },
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": normalized,
                                    },
                                    "region": {"startLine": 1},
                                },
                            }
                        ],
                        "partialFingerprints": {
                            "primaryLocationLineHash": fingerprint,
                        },
                    }
                )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "OWASP ZAP",
                        "informationUri": "https://www.zaproxy.org/",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.sarif>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    try:
        with open(input_path) as f:
            zap_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON in {input_path}: {exc}")
        sys.exit(1)

    sarif = convert(zap_data)

    with open(output_path, "w") as f:
        json.dump(sarif, f, indent=2)

    alert_count = len(sarif["runs"][0]["results"])
    rule_count = len(sarif["runs"][0]["tool"]["driver"]["rules"])
    print(f"Converted {alert_count} findings ({rule_count} rules) to {output_path}")


if __name__ == "__main__":
    main()
