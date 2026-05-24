# Changelog

All notable changes to this project are documented here.

## [0.1.0] — 2026-05-24

First public research preview.

### Added

- Three-phase deliberation pipeline (sealed exploration, stress-test loop, verdicts)
- Claim graph with claims, evidence, edges, and embedding-based deduplication
- Council agents, arbiter, and observer roles via OpenRouter
- Version B manipulation experiment (disguised self-reinforcement injection)
- CLI: `council run` and `council experiment`
- Mock provider for dry runs (`--mock`)
- Artifact output under `runs/` (graphs, transcripts, verdicts, cost summary)
- Documentation: README, `docs/ARCHITECTURE.md`, `docs/KNOWN_LIMITATIONS.md`
- GitHub Actions CI (pytest + mock smoke test on Python 3.9, 3.11, 3.12)

### Security

- Config snapshots redact API keys before writing to `runs/*/config.yaml`

### Known issues

See [README](README.md#known-limitations) and [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).
