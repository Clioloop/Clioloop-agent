# Migrating from Hermes Agent to Clio Agent

Clio Agent is maintained by **Omni Loop Labs**. Migration is additive: existing
Clio locales, profiles, plugins, sessions, and managed-provider settings are not
removed or renamed merely to match upstream.

## Before migrating

1. Stop only the process you intend to migrate; do not delete `~/.clio`.
2. Back up the profile directory and record the installed commit.
3. Run `python scripts/scan_upstream_parity.py --upstream /path/to/hermes-agent`.
   The scanner is read-only and never merges upstream code.

## Mapping

- Hermes home/config values should be copied deliberately into `~/.clio/config.yaml`.
- Keep Clio command names (`clio`, `clio gateway`, `clio plugins`) and Omni Loop
  Portal/managed-provider configuration. Do not bulk-replace product names.
- Reinstall plugins under the matching Clio profile. Review requested hooks and
  capabilities rather than copying executable plugin state blindly.
- Validate skills with `python scripts/lint_skills.py /path/to/skills` before use.
- Arabic is `display.language: ar`; web and desktop set `lang=ar` and `dir=rtl`.
  Existing English, Chinese, and all web locales remain supported.

## Verification and rollback

Run the local release checks in [testing-release-closure.md](testing-release-closure.md).
The shell installer records the pre-update Git revision and restores it if the
fetch/checkout/fast-forward update fails. User modifications are stashed first
and remain recoverable. Keep the backup until the agent, gateway, and chosen UI
have passed smoke tests.
