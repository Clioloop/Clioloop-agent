import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], cwd=ROOT, text=True, capture_output=True, check=False)

def test_generated_references_are_current():
    result = run_script("generate_references.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr

def test_skill_dependency_and_release_policy():
    for script in ("lint_skills.py", "verify_dependency_policy.py", "verify_release_metadata.py"):
        result = run_script(script)
        assert result.returncode == 0, result.stdout + result.stderr

def test_parity_scanner_is_json_and_read_only():
    before = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    result = run_script("scan_upstream_parity.py", "--local", str(ROOT), "--upstream", str(ROOT))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mode"] == "read-only"
    assert report["auto_merge"] is False
    assert report["comparison"]["files"]["upstream_only"] == []
    after = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    assert after == before

def test_installer_has_transaction_rollback_and_runtime_healing():
    installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts/lib/node-bootstrap.sh").read_text(encoding="utf-8")
    assert "previous_head=$(git rev-parse HEAD)" in installer
    assert 'git reset --hard "$previous_head"' in installer
    assert "npm --version" in bootstrap
    assert "node.rollback.$$" in bootstrap

def test_node_health_check_rejects_runtime_without_npm(tmp_path: Path):
    node = tmp_path / "node"
    node.write_text("#!/bin/sh\n[ \"$1\" = --version ] && echo v22.1.0\nexit 0\n", encoding="utf-8")
    node.chmod(0o755)
    probe = subprocess.run(
        ["/bin/bash", "-c", "source scripts/lib/node-bootstrap.sh; _nb_have_modern_node"],
        cwd=ROOT,
        env={"PATH": str(tmp_path), "HOME": str(tmp_path)},
        check=False,
    )
    assert probe.returncode != 0
