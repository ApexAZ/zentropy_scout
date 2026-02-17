"""Convert ZAP Traditional JSON report to SARIF 2.1.0 for GitHub Security tab.

Usage: python zap-to-sarif.py <input.json> <output.sarif>

ZAP's API scan produces a Traditional JSON report but not SARIF. This script
bridges the gap so DAST findings appear alongside Trivy results in the GitHub
Security tab (private, unlike GitHub Issues).

Since DAST results target URLs rather than source files, each location uses
the endpoint path as the artifact URI and startLine=1 as a placeholder.
"""

import json
import re
import sys


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
    """Strip protocol, host, and port from a URL to get the path."""
    return re.sub(r"^\w+://[^/]+(:\d+)?", "", uri) or "/"


def convert(zap_json: dict) -> dict:
    """Convert ZAP JSON report to SARIF 2.1.0 format."""
    rules: list[dict] = []
    results: list[dict] = []
    seen_rule_ids: set[str] = set()

    for site in zap_json.get("site", []):
        for alert in site.get("alerts", []):
            rule_id = str(alert.get("alertRef", alert.get("pluginid", "0")))

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
