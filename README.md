# miniflux-feed-dedup

Dedup proxy for the eFinancialCareers RSS feed, published to GHCR and
auto-updated by Watchtower (scope `nick`).

The upstream feed
(`https://www.efinancialcareers.com/feed/syndication/rss.xml`) frequently
publishes the same article multiple times under different URLs (slug rewrites,
old `/news/2014/09/...` date paths, `/finance/` variants, trailing `-sc`,
etc.). Miniflux deduplicates entries by URL hash, so every URL alias becomes a
separate story in the reader. This service fetches the upstream feed, removes
duplicate items (same normalized title) preferring the most canonical-looking
URL, and serves the cleaned feed to Miniflux.

Endpoints:
- `GET /rss.xml` — cleaned feed (application/rss+xml)
- `GET /healthz` — health check

## Deploy (NAS)

```bash
docker compose up -d     # import docker-compose.yml as a Container Manager "Project"
```

Miniflux subscribes to `http://127.0.0.1:8090/rss.xml` (published host port).

On push to `main`, CircleCI publishes `ghcr.io/nickbrett1/miniflux-feed-dedup:latest`;
`watchtower-nick` picks it up within ~60s.

## Files

- `dedup.py` — the stdlib-only dedup HTTP server (no third-party deps).
- `Dockerfile` — thin `python:3.12-alpine` image running `dedup.py`.
- `docker-compose.yml` — NAS deployment (host port 8090, scope `nick`).

## Code quality / CI

- `.circleci/config.yml` — `build` (ruff + pytest) gating `docker-publish` on `main`.
- Uses the `common` CircleCI context for `GHCR_USERNAME` / `GHCR_TOKEN`.
