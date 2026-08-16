# Release-closure testing

All checks are local and make no network calls unless an explicit upstream path
is supplied from an already available checkout.

```bash
python scripts/generate_references.py --check
python scripts/lint_skills.py
python scripts/verify_dependency_policy.py
python scripts/verify_release_metadata.py
python scripts/scan_upstream_parity.py \
  --local . --upstream /tmp/hermes-agent-audit > /tmp/parity.json
python -m json.tool /tmp/parity.json >/dev/null
bash -n scripts/install.sh scripts/lib/node-bootstrap.sh
npm --workspace web run build
npm --workspace apps/desktop run type-check
```

`config/ci-shards.json` is the machine-readable test split. Every shard has a
stable id, bounded timeout, and either test paths or an explicit command.

## Provenance and licenses

`config/provenance.json` records audited upstreams, pinned revisions, licenses,
and how material is used. `verify_release_metadata.py` checks that it agrees
with `LICENSE`, `pyproject.toml`, `package.json`, and the shard contract. The
parity scanner only emits evidence; adoption remains a reviewed human change.

## Installer recovery checks

The update path preserves the old branch/revision, stashes user edits, and rolls
back a failed fetch/checkout/pull. Node readiness requires both a runnable Node
process and npm; a corrupt Clio-managed runtime is quarantined before healing.
Tests should use temporary repositories/homes and must not restart services.
