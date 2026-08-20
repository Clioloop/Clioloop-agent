"""Offline acceptance tests for the bundled grounded-citations skill."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parents[2]
    / "skills"
    / "research"
    / "grounded-citations"
    / "scripts"
    / "source_ledger.py"
)
SKILL = SCRIPT.parents[1] / "SKILL.md"


def load_module():
    spec = importlib.util.spec_from_file_location("clio_grounded_citations", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_is_clio_native_and_documents_verification():
    content = SKILL.read_text(encoding="utf-8")
    assert "author: Clio Agent" in content
    assert "exact supporting quote" in content
    assert "never credentials" in content
    assert "Hermes" not in content


def test_add_source_requires_exact_normalized_quote():
    module = load_module()
    ledger = module.empty_ledger()
    row = module.add_source(
        ledger,
        url="https://example.com/report",
        title="Report",
        claim="The value is 41.",
        quote="The value is 41.",
        content="Header\n\nThe   value is 41.\nFooter",
        retrieved_at="2026-08-20T00:00:00+00:00",
    )
    assert row["id"] == "S1"
    assert row["quote_sha256"] == module.quote_digest("The value is 41.")
    assert module.validate_ledger(ledger) == []

    with pytest.raises(ValueError, match="not found"):
        module.add_source(
            ledger,
            url="https://example.com/other",
            title="Other",
            claim="Unsupported claim",
            quote="This text is absent",
            content="No matching evidence here",
        )


def test_credential_bearing_url_is_rejected():
    module = load_module()
    with pytest.raises(ValueError, match="credentials"):
        module.validate_url("https://user:secret@example.com/report")


def test_cli_round_trip_and_tamper_detection(tmp_path, capsys):
    module = load_module()
    ledger_path = tmp_path / "sources.json"
    content_path = tmp_path / "page.txt"
    content_path.write_text("A regulator published 41 incidents.", encoding="utf-8")

    assert module.main(["init", str(ledger_path)]) == 0
    assert module.main(
        [
            "add",
            str(ledger_path),
            "--url",
            "https://example.com/incidents",
            "--title",
            "Incident report",
            "--claim",
            "The regulator published 41 incidents.",
            "--quote",
            "A regulator published 41 incidents.",
            "--content-file",
            str(content_path),
        ]
    ) == 0
    assert module.main(["verify", str(ledger_path)]) == 0
    assert module.main(["render", str(ledger_path)]) == 0
    output = capsys.readouterr().out
    assert "[S1] Incident report" in output

    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    data["sources"][0]["quote"] = "tampered"
    ledger_path.write_text(json.dumps(data), encoding="utf-8")
    assert module.main(["verify", str(ledger_path)]) == 1
