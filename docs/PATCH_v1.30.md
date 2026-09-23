# Dugout Atlas v1.30 — Security, Reliability & UX

- HTTP: retry only transient statuses 408/425/429/5xx, honor Retry-After (capped at 60 seconds), exponential backoff with jitter; reuse session across attempts.
- HTTP: bounded streaming reads (JSON 20 MiB, MLB logo 5 MiB, CSV/text 100 MiB), connect/read timeouts, no response-body logging.
- B-Ref imports: cap ZIP members (50), aggregate expanded size (250 MiB), per-member size (100 MiB), compression ratio (200:1); validate year and WAR numeric values. Do not unpack onto disk. Imported source metadata records filename only.
- Logs: redact URL queries, common credentials and user home directory paths.
- Player source panel shows availability even when a source returned no data. Explicit refresh control reloads game and selected player.
- CI gates: critical Ruff rules, pytest, Bandit medium/high findings, pip-audit, metadata smoke test. Release direct dependencies are pinned by `constraints-release.txt`.

Existing FanGraphs/B-Ref/Statcast statistic calculation and player matching implementations were not changed. App/package version is 1.30. This is source distribution; no signed Windows installer is provided.
