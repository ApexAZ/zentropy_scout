"""Tests for ZAP-to-SARIF converter.

VULN-002: The converter had 4 bugs causing misclassified alerts in the
GitHub Security tab. These tests verify the reworked converter.
"""

import importlib.util
import sys
from pathlib import Path

# Import the converter module from its non-package location
_SCRIPT_PATH = Path(__file__).parent / "zap-to-sarif.py"
_spec = importlib.util.spec_from_file_location("zap_to_sarif", _SCRIPT_PATH)
_module = importlib.util.module_from_spec(_spec)
sys.modules["zap_to_sarif"] = _module
_spec.loader.exec_module(_module)

convert = _module.convert
_parse_risk = _module._parse_risk
_risk_to_sarif_level = _module._risk_to_sarif_level
_make_rule_id = _module._make_rule_id
_strip_html = _module._strip_html
_uri_to_path = _module._uri_to_path
_normalize_path_segment = _module._normalize_path_segment
_normalize_path = _module._normalize_path
_compute_fingerprint = _module._compute_fingerprint


# =============================================================================
# Fixtures
# =============================================================================


def _make_alert(
    *,
    name: str = "Test Alert",
    pluginid: str = "12345",
    alert_ref: str | None = None,
    riskdesc: str = "Medium (Medium)",
    desc: str = "Test description",
    cweid: str = "79",
    instances: list[dict] | None = None,
) -> dict:
    """Build a minimal ZAP alert dict for testing."""
    alert = {
        "name": name,
        "pluginid": pluginid,
        "alertRef": alert_ref or pluginid,
        "riskdesc": riskdesc,
        "desc": desc,
        "cweid": cweid,
        "instances": instances or [{"uri": "http://localhost/api/v1/test", "method": "GET"}],
    }
    return alert


def _make_zap_report(*alerts: dict) -> dict:
    """Wrap alerts in a ZAP JSON report structure."""
    return {"site": [{"alerts": list(alerts)}]}


# =============================================================================
# _parse_risk tests
# =============================================================================


class TestParseRisk:
    """Tests for _parse_risk() — extract risk level from riskdesc string."""

    def test_low_risk_high_confidence(self):
        """'Low (High)' should extract risk 'low', not 'high'."""
        assert _parse_risk("Low (High)") == "low"

    def test_informational_high_confidence(self):
        """'Informational (High)' should extract 'informational', not 'high'.

        This was Bug 2: the old _severity() matched 'high' as a substring.
        """
        assert _parse_risk("Informational (High)") == "informational"

    def test_medium_medium(self):
        assert _parse_risk("Medium (Medium)") == "medium"

    def test_high_low(self):
        assert _parse_risk("High (Low)") == "high"

    def test_empty_string(self):
        assert _parse_risk("") == "informational"

    def test_no_parenthesis(self):
        assert _parse_risk("Low") == "low"


# =============================================================================
# _risk_to_sarif_level tests
# =============================================================================


class TestRiskToSarifLevel:
    """Tests for _risk_to_sarif_level() — map risk to SARIF severity."""

    def test_high_maps_to_error(self):
        assert _risk_to_sarif_level("high") == "error"

    def test_medium_maps_to_warning(self):
        assert _risk_to_sarif_level("medium") == "warning"

    def test_low_maps_to_warning(self):
        assert _risk_to_sarif_level("low") == "warning"

    def test_informational_maps_to_note(self):
        assert _risk_to_sarif_level("informational") == "note"

    def test_unknown_maps_to_note(self):
        assert _risk_to_sarif_level("unknown") == "note"


# =============================================================================
# _make_rule_id tests
# =============================================================================


class TestMakeRuleId:
    """Tests for _make_rule_id() — generate unique rule IDs."""

    def test_normal_alert_uses_alert_ref(self):
        """Non-100000 alerts should use alertRef as rule ID."""
        alert = _make_alert(pluginid="30002", alert_ref="30002")
        assert _make_rule_id(alert) == "30002"

    def test_server_error_gets_suffix(self):
        """Server Error (100000) should get '-server' suffix.

        This was Bug 1: both client and server shared rule ID '100000'.
        """
        alert = _make_alert(
            name="A Server Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
        )
        assert _make_rule_id(alert) == "100000-server"

    def test_client_error_gets_suffix(self):
        """Client Error (100000) should get '-client' suffix."""
        alert = _make_alert(
            name="A Client Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
        )
        assert _make_rule_id(alert) == "100000-client"

    def test_unknown_100000_gets_name_suffix(self):
        """Unknown 100000 alert name should get a sanitized name suffix."""
        alert = _make_alert(
            name="Some Other 100000 Alert",
            pluginid="100000",
            alert_ref="100000",
        )
        result = _make_rule_id(alert)
        assert result.startswith("100000-")
        assert result != "100000-client"
        assert result != "100000-server"

    def test_unknown_100000_no_name_uses_base_id(self):
        """100000 alert with no name should fall back to base ID."""
        alert = {"pluginid": "100000", "alertRef": "100000", "name": ""}
        assert _make_rule_id(alert) == "100000"

    def test_falls_back_to_pluginid(self):
        """If alertRef is missing, should use pluginid."""
        alert = {"name": "Test", "pluginid": "99999"}
        assert _make_rule_id(alert) == "99999"


# =============================================================================
# convert() integration tests
# =============================================================================


class TestConvert:
    """Integration tests for the full convert() function."""

    def test_separate_rules_for_client_and_server_errors(self):
        """Bug 1 fix: client and server 100000 alerts get separate SARIF rules."""
        server_alert = _make_alert(
            name="A Server Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
            riskdesc="Low (High)",
        )
        client_alert = _make_alert(
            name="A Client Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
            riskdesc="Informational (High)",
        )
        report = _make_zap_report(server_alert, client_alert)
        sarif = convert(report)

        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = {r["id"] for r in rules}
        assert "100000-server" in rule_ids
        assert "100000-client" in rule_ids
        assert len(rules) == 2

    def test_informational_alert_gets_note_severity(self):
        """Bug 2 fix: 'Informational (High)' should map to 'note', not 'error'."""
        alert = _make_alert(
            name="A Client Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
            riskdesc="Informational (High)",
        )
        sarif = convert(_make_zap_report(alert))

        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        assert rules[0]["defaultConfiguration"]["level"] == "note"

    def test_per_result_level_field(self):
        """Bug 3 fix: each result should have a 'level' field."""
        alert = _make_alert(riskdesc="Medium (Medium)")
        sarif = convert(_make_zap_report(alert))

        results = sarif["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["level"] == "warning"

    def test_per_result_level_matches_alert_risk(self):
        """Per-result level should reflect the parent alert's risk, not the rule default."""
        server_alert = _make_alert(
            name="A Server Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
            riskdesc="Low (High)",
            instances=[{"uri": "http://localhost/api/v1/flags?status=%00", "method": "GET"}],
        )
        client_alert = _make_alert(
            name="A Client Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
            riskdesc="Informational (High)",
            instances=[{"uri": "http://localhost/api/v1/test", "method": "GET"}],
        )
        sarif = convert(_make_zap_report(server_alert, client_alert))

        results = sarif["runs"][0]["results"]
        server_results = [r for r in results if r["ruleId"] == "100000-server"]
        client_results = [r for r in results if r["ruleId"] == "100000-client"]

        assert all(r["level"] == "warning" for r in server_results)
        assert all(r["level"] == "note" for r in client_results)

    def test_help_uri_uses_pluginid_not_rule_id(self):
        """helpUri should use the original pluginid, not the suffixed rule ID."""
        alert = _make_alert(
            name="A Server Error response code was returned by the server",
            pluginid="100000",
            alert_ref="100000",
        )
        sarif = convert(_make_zap_report(alert))

        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        assert rules[0]["helpUri"] == "https://www.zaproxy.org/docs/alerts/100000/"

    def test_sarif_schema_version(self):
        """Output should be valid SARIF 2.1.0."""
        sarif = convert(_make_zap_report(_make_alert()))
        assert sarif["version"] == "2.1.0"
        assert sarif["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"

    def test_empty_report_produces_empty_results(self):
        """Empty ZAP report should produce valid SARIF with no results."""
        sarif = convert({"site": []})
        assert sarif["runs"][0]["results"] == []
        assert sarif["runs"][0]["tool"]["driver"]["rules"] == []

    def test_result_message_includes_method_and_uri(self):
        """Result message should include HTTP method and full URI."""
        alert = _make_alert(
            name="Test Alert",
            instances=[{"uri": "http://localhost:8000/api/v1/test", "method": "POST"}],
        )
        sarif = convert(_make_zap_report(alert))
        msg = sarif["runs"][0]["results"][0]["message"]["text"]
        assert "POST" in msg
        assert "http://localhost:8000/api/v1/test" in msg

    def test_cwe_tag_in_rule_properties(self):
        """Rule properties should include CWE tag."""
        alert = _make_alert(cweid="89")
        sarif = convert(_make_zap_report(alert))
        rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
        assert "external/cwe/cwe-89" in rule["properties"]["tags"]


# =============================================================================
# Existing function tests (no regressions)
# =============================================================================


class TestStripHtml:
    """Tests for _strip_html() helper."""

    def test_strips_html_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_preserves_plain_text(self):
        assert _strip_html("No tags here") == "No tags here"


class TestUriToPath:
    """Tests for _uri_to_path() helper."""

    def test_extracts_path_from_url(self):
        assert _uri_to_path("http://localhost:8000/api/v1/test") == "/api/v1/test"

    def test_strips_query_string(self):
        assert _uri_to_path("http://localhost/api?q=1") == "/api"

    def test_returns_slash_for_root(self):
        assert _uri_to_path("http://localhost:8000") == "/"


# =============================================================================
# _normalize_path_segment tests
# =============================================================================


class TestNormalizePathSegment:
    """Tests for _normalize_path_segment() — replace dynamic segments with {id}."""

    def test_replaces_large_number(self):
        """ZAP fuzz payloads (10+ digit numbers) should become {id}."""
        assert _normalize_path_segment("8297929860933747743") == "{id}"

    def test_replaces_uuid(self):
        """Standard UUID should become {id}."""
        assert _normalize_path_segment("550e8400-e29b-41d4-a716-446655440000") == "{id}"

    def test_replaces_uppercase_uuid(self):
        """Uppercase UUID should also become {id}."""
        assert _normalize_path_segment("550E8400-E29B-41D4-A716-446655440000") == "{id}"

    def test_preserves_named_segment(self):
        """Named path segments like 'resume_id' should not be replaced."""
        assert _normalize_path_segment("resume_id") == "resume_id"

    def test_preserves_api_prefix(self):
        assert _normalize_path_segment("api") == "api"

    def test_preserves_version(self):
        """Short version numbers should not be replaced."""
        assert _normalize_path_segment("v1") == "v1"

    def test_preserves_short_number(self):
        """Numbers under 10 digits should not be replaced."""
        assert _normalize_path_segment("12345") == "12345"

    def test_preserves_nine_digit_number(self):
        """9-digit numbers are below the threshold."""
        assert _normalize_path_segment("123456789") == "123456789"

    def test_replaces_ten_digit_number(self):
        """10-digit numbers hit the threshold."""
        assert _normalize_path_segment("1234567890") == "{id}"

    def test_preserves_kebab_case_name(self):
        """Kebab-case endpoint names should not be replaced."""
        assert _normalize_path_segment("job-postings") == "job-postings"

    def test_preserves_empty_segment(self):
        """Empty segments (from leading slash) should pass through."""
        assert _normalize_path_segment("") == ""


# =============================================================================
# _normalize_path tests
# =============================================================================


class TestNormalizePath:
    """Tests for _normalize_path() — normalize full URL paths."""

    def test_normalizes_zap_payload_in_path(self):
        """ZAP payload number should be replaced with {id}."""
        assert _normalize_path("api/v1/personas/8297929860933747743") == "api/v1/personas/{id}"

    def test_normalizes_uuid_in_path(self):
        """UUID in path should be replaced with {id}."""
        path = "api/v1/personas/550e8400-e29b-41d4-a716-446655440000"
        assert _normalize_path(path) == "api/v1/personas/{id}"

    def test_preserves_named_segments(self):
        """Named segments like 'variant_id' should be preserved."""
        path = "api/v1/job-variants/variant_id/3811768465121217484"
        assert _normalize_path(path) == "api/v1/job-variants/variant_id/{id}"

    def test_normalizes_multiple_dynamic_segments(self):
        """Multiple dynamic segments should all be replaced."""
        path = "api/v1/personas/1234567890/skills/9876543210"
        assert _normalize_path(path) == "api/v1/personas/{id}/skills/{id}"

    def test_preserves_static_path(self):
        """Paths with no dynamic segments should be unchanged."""
        assert _normalize_path("api/v1/personas") == "api/v1/personas"

    def test_handles_leading_slash(self):
        """Leading slash should be preserved."""
        assert _normalize_path("/api/v1/test/1234567890") == "/api/v1/test/{id}"

    def test_handles_root_path(self):
        assert _normalize_path("/") == "/"

    def test_handles_empty_string(self):
        assert _normalize_path("") == ""


# =============================================================================
# _compute_fingerprint tests
# =============================================================================


class TestComputeFingerprint:
    """Tests for _compute_fingerprint() — stable SARIF fingerprints."""

    def test_returns_string_with_suffix(self):
        """Fingerprint should be a hex string ending with ':1'."""
        fp = _compute_fingerprint("10038", "GET", "api/v1/personas")
        assert fp.endswith(":1")
        # 16 hex chars + ":1" = 18 chars
        assert len(fp) == 18

    def test_same_input_same_output(self):
        """Identical inputs should produce identical fingerprints."""
        fp1 = _compute_fingerprint("10038", "GET", "api/v1/personas")
        fp2 = _compute_fingerprint("10038", "GET", "api/v1/personas")
        assert fp1 == fp2

    def test_different_methods_different_fingerprints(self):
        """GET vs POST on the same endpoint should differ."""
        fp_get = _compute_fingerprint("10038", "GET", "api/v1/personas")
        fp_post = _compute_fingerprint("10038", "POST", "api/v1/personas")
        assert fp_get != fp_post

    def test_different_rules_different_fingerprints(self):
        """Different rule IDs on the same endpoint should differ."""
        fp1 = _compute_fingerprint("10038", "GET", "api/v1/personas")
        fp2 = _compute_fingerprint("40018", "GET", "api/v1/personas")
        assert fp1 != fp2

    def test_different_paths_different_fingerprints(self):
        """Different endpoints should produce different fingerprints."""
        fp1 = _compute_fingerprint("10038", "GET", "api/v1/personas")
        fp2 = _compute_fingerprint("10038", "GET", "api/v1/job-postings")
        assert fp1 != fp2

    def test_hex_characters_only(self):
        """The hash portion should be lowercase hex."""
        fp = _compute_fingerprint("10038", "GET", "api/v1/test")
        hash_part = fp.split(":")[0]
        assert all(c in "0123456789abcdef" for c in hash_part)


# =============================================================================
# Integration: fingerprints in SARIF output
# =============================================================================


class TestSarifFingerprints:
    """Integration tests: fingerprints and normalized paths in SARIF output."""

    def test_fingerprint_present_in_results(self):
        """Every result should include partialFingerprints."""
        alert = _make_alert(
            instances=[{"uri": "http://localhost/api/v1/personas/123456789012", "method": "GET"}],
        )
        sarif = convert(_make_zap_report(alert))
        result = sarif["runs"][0]["results"][0]

        assert "partialFingerprints" in result
        assert "primaryLocationLineHash" in result["partialFingerprints"]
        assert len(result["partialFingerprints"]["primaryLocationLineHash"]) > 0

    def test_normalized_uri_in_artifact_location(self):
        """Artifact URI should use {id} instead of ZAP payload numbers."""
        alert = _make_alert(
            instances=[{"uri": "http://localhost/api/v1/personas/8297929860933747743", "method": "GET"}],
        )
        sarif = convert(_make_zap_report(alert))
        uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]

        assert uri == "api/v1/personas/{id}"
        assert "8297929860933747743" not in uri

    def test_raw_uri_preserved_in_message(self):
        """The full original URI (with ZAP payload) should still appear in the message."""
        full_uri = "http://localhost/api/v1/personas/8297929860933747743"
        alert = _make_alert(instances=[{"uri": full_uri, "method": "GET"}])
        sarif = convert(_make_zap_report(alert))
        msg = sarif["runs"][0]["results"][0]["message"]["text"]

        assert full_uri in msg

    def test_same_endpoint_different_payloads_same_fingerprint(self):
        """The core dedup test: different ZAP payloads for the same endpoint
        should produce identical fingerprints."""
        alert1 = _make_alert(
            pluginid="100000",
            alert_ref="100000",
            name="A Client Error response code was returned by the server",
            riskdesc="Informational (High)",
            instances=[{"uri": "http://localhost/api/v1/personas/1111111111111111111", "method": "GET"}],
        )
        alert2 = _make_alert(
            pluginid="100000",
            alert_ref="100000",
            name="A Client Error response code was returned by the server",
            riskdesc="Informational (High)",
            instances=[{"uri": "http://localhost/api/v1/personas/9999999999999999999", "method": "GET"}],
        )
        sarif1 = convert(_make_zap_report(alert1))
        sarif2 = convert(_make_zap_report(alert2))

        fp1 = sarif1["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]
        fp2 = sarif2["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]
        assert fp1 == fp2

    def test_different_endpoints_different_fingerprints(self):
        """Different endpoints should produce different fingerprints in SARIF."""
        alert_personas = _make_alert(
            instances=[{"uri": "http://localhost/api/v1/personas/1234567890", "method": "GET"}],
        )
        alert_jobs = _make_alert(
            instances=[{"uri": "http://localhost/api/v1/job-postings/1234567890", "method": "GET"}],
        )
        sarif = convert(_make_zap_report(alert_personas, alert_jobs))
        results = sarif["runs"][0]["results"]

        fp1 = results[0]["partialFingerprints"]["primaryLocationLineHash"]
        fp2 = results[1]["partialFingerprints"]["primaryLocationLineHash"]
        assert fp1 != fp2
