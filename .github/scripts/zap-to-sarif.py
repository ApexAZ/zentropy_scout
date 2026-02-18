"""Convert ZAP Traditional JSON report to SARIF 2.1.0 for GitHub Security tab.

Usage: python zap-to-sarif.py <input.json> <output.sarif> [rules.tsv]

ZAP's API scan produces a Traditional JSON report but not SARIF. This script
bridges the gap so DAST findings appear alongside Trivy results in the GitHub
Security tab (private, unlike GitHub Issues).

When a rules TSV file is provided (same format as ZAP's rules_file_name),
any rule marked IGNORE is excluded from the SARIF output. This prevents
informational alerts (e.g. 4xx responses on invalid IDs) from flooding the
GitHub Security tab.

Since DAST results target URLs rather than source files, each location uses
the endpoint path as the artifact URI and startLine=1 as a placeholder.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _strip_html(text: str) -> str:
    """Remove HTML tags from ZAP descriptions."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _severity(riskdesc: str) -> str:
    """Map ZAP riskdesc string to SARIF severity level."""
    lower = riskdesc.lower()
    if "high" in lower:
        return "error"
    if "medium" in lower:
        return "warning"
    if "low" in lower:
        return "warning"
    return "note"


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


def parse_rules_tsv(tsv_path: str) -> set[str]:
    """Parse a ZAP rules TSV file and return rule IDs marked IGNORE.

    Format: ``<rule_id>\\t<action>\\t<optional description>``
    Lines starting with # are comments.
    """
    ignored: set[str] = set()
    path = Path(tsv_path)
    if not path.is_file():
        print(f"Warning: Rules file not found: {tsv_path}, no rules will be filtered")
        return ignored

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip().upper() == "IGNORE":
            ignored.add(parts[0].strip())

    return ignored


def convert(
    zap_json: dict, ignored_rules: set[str] | None = None
) -> tuple[dict, int]:
    """Convert ZAP JSON report to SARIF 2.1.0 format.

    Args:
        zap_json: Parsed ZAP Traditional JSON report.
        ignored_rules: Rule IDs to exclude from SARIF output.

    Returns:
        Tuple of (SARIF dict, number of skipped alert instances).
    """
    if ignored_rules is None:
        ignored_rules = set()

    rules: list[dict] = []
    results: list[dict] = []
    seen_rule_ids: set[str] = set()
    skipped = 0

    for site in zap_json.get("site", []):
        for alert in site.get("alerts", []):
            rule_id = str(alert.get("alertRef", alert.get("pluginid", "0")))

            if rule_id in ignored_rules:
                skipped += len(alert.get("instances", []))
                continue

            if rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule_id)
                rules.append(
                    {
                        "id": rule_id,
                        "shortDescription": {"text": alert.get("name", "")},
                        "fullDescription": {
                            "text": _strip_html(alert.get("desc", ""))
                        },
                        "helpUri": f"https://www.zaproxy.org/docs/alerts/{rule_id}/",
                        "defaultConfiguration": {
                            "level": _severity(alert.get("riskdesc", ""))
                        },
                        "properties": {
                            "tags": [f"external/cwe/cwe-{alert.get('cweid', '0')}"]
                        },
                    }
                )

            for instance in alert.get("instances", []):
                uri = instance.get("uri", "")
                method = instance.get("method", "GET")
                results.append(
                    {
                        "ruleId": rule_id,
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
                                        "uri": _uri_to_path(uri).lstrip("/")
                                        or "api",
                                    },
                                    "region": {"startLine": 1},
                                },
                            }
                        ],
                    }
                )

    sarif = {
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
    return sarif, skipped


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print(f"Usage: {sys.argv[0]} <input.json> <output.sarif> [rules.tsv]")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]
    rules_path = sys.argv[3] if len(sys.argv) == 4 else None

    ignored_rules: set[str] = set()
    if rules_path:
        ignored_rules = parse_rules_tsv(rules_path)
        if ignored_rules:
            print(f"Filtering {len(ignored_rules)} ignored rules: {', '.join(sorted(ignored_rules))}")

    try:
        with open(input_path) as f:
            zap_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON in {input_path}: {exc}")
        sys.exit(1)

    sarif, skipped_count = convert(zap_data, ignored_rules=ignored_rules)

    with open(output_path, "w") as f:
        json.dump(sarif, f, indent=2)

    alert_count = len(sarif["runs"][0]["results"])
    rule_count = len(sarif["runs"][0]["tool"]["driver"]["rules"])
    msg = f"Converted {alert_count} findings ({rule_count} rules) to {output_path}"
    if skipped_count:
        msg += f" (filtered {skipped_count} ignored)"
    print(msg)


if __name__ == "__main__":
    main()
