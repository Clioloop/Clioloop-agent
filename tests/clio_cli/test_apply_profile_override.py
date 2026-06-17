"""Regression tests for _apply_profile_override CLIO_HOME guard (issue #22502).

When CLIO_HOME is set to the clio root (e.g. systemd hardcodes
CLIO_HOME=/root/.clio), _apply_profile_override must still read
active_profile and update CLIO_HOME to the profile directory.

When CLIO_HOME is already a profile directory (.../profiles/<name>),
_apply_profile_override must trust it and return without re-reading
active_profile (child-process inheritance contract).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path



def _run_apply_profile_override(
    tmp_path, monkeypatch, *, clio_home: str | None, active_profile: str | None,
    argv: list[str] | None = None,
):
    """Run _apply_profile_override in isolation.

    Returns the value of os.environ["CLIO_HOME"] after the call,
    or None if unset.
    """
    clio_root = tmp_path / ".clio"
    clio_root.mkdir(parents=True, exist_ok=True)

    if active_profile is not None:
        (clio_root / "active_profile").write_text(active_profile)

    if active_profile and active_profile != "default":
        (clio_root / "profiles" / active_profile).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if clio_home is not None:
        monkeypatch.setenv("CLIO_HOME", clio_home)
    else:
        monkeypatch.delenv("CLIO_HOME", raising=False)

    monkeypatch.setattr(sys, "argv", argv or ["clio", "gateway", "start"])

    from clio_cli.main import _apply_profile_override
    _apply_profile_override()

    return os.environ.get("CLIO_HOME")


class TestApplyProfileOverrideClioHomeGuard:
    """Regression guard for issue #22502.

    Verifies that CLIO_HOME pointing to the clio root does NOT suppress
    the active_profile check, while CLIO_HOME already pointing to a
    profile directory IS trusted as-is.
    """

    def test_clio_home_at_root_with_active_profile_is_redirected(
        self, tmp_path, monkeypatch
    ):
        """CLIO_HOME=/root/.clio + active_profile=coder must redirect
        CLIO_HOME to .../profiles/coder.

        Bug scenario from #22502: systemd sets CLIO_HOME to the clio root
        and the user switches to a profile via `clio profile use`.
        Before the fix, the guard returned early and active_profile was ignored.
        """
        clio_root = tmp_path / ".clio"
        clio_root.mkdir(parents=True, exist_ok=True)

        result = _run_apply_profile_override(
            tmp_path,
            monkeypatch,
            clio_home=str(clio_root),
            active_profile="coder",
        )

        assert result is not None, "CLIO_HOME must be set after profile redirect"
        assert "profiles" in result, (
            f"Expected CLIO_HOME to point into profiles/ dir, got: {result!r}"
        )
        assert result.endswith("coder"), (
            f"Expected CLIO_HOME to end with 'coder', got: {result!r}"
        )

    def test_clio_home_already_profile_dir_is_trusted(self, tmp_path, monkeypatch):
        """CLIO_HOME=.../profiles/coder must not be overridden even when
        active_profile says something different.

        Preserves the child-process inheritance contract: a subprocess spawned
        with CLIO_HOME already set to a specific profile must stay in that
        profile.
        """
        clio_root = tmp_path / ".clio"
        profile_dir = clio_root / "profiles" / "coder"
        profile_dir.mkdir(parents=True, exist_ok=True)

        (clio_root / "active_profile").write_text("other")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("CLIO_HOME", str(profile_dir))
        monkeypatch.setattr(sys, "argv", ["clio", "gateway", "start"])

        from clio_cli.main import _apply_profile_override
        _apply_profile_override()

        assert os.environ.get("CLIO_HOME") == str(profile_dir), (
            "CLIO_HOME must remain unchanged when already pointing to a profile dir"
        )

    def test_clio_home_unset_reads_active_profile(self, tmp_path, monkeypatch):
        """Classic case: CLIO_HOME unset + active_profile=coder must set
        CLIO_HOME to the profile directory (existing behaviour must not regress).
        """
        result = _run_apply_profile_override(
            tmp_path,
            monkeypatch,
            clio_home=None,
            active_profile="coder",
        )

        assert result is not None
        assert "coder" in result

    def test_clio_home_unset_default_profile_no_redirect(self, tmp_path, monkeypatch):
        """active_profile=default must not redirect CLIO_HOME."""
        clio_root = tmp_path / ".clio"
        clio_root.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("CLIO_HOME", raising=False)
        monkeypatch.setattr(sys, "argv", ["clio", "gateway", "start"])
        (clio_root / "active_profile").write_text("default")

        from clio_cli.main import _apply_profile_override
        _apply_profile_override()

        assert os.environ.get("CLIO_HOME") is None
