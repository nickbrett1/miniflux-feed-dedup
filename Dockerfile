# miniflux-feed-dedup
#
# Self-contained image running dedup.py (stdlib-only HTTP RSS dedup proxy for
# the eFinancialCareers feed). Published to GHCR by CircleCI and auto-updated
# by watchtower-nick (scope=nick, 60s poll).
FROM python:3.12-alpine

# Link the GHCR package to this repo (public repo -> public package).
LABEL org.opencontainers.image.source=https://github.com/nickbrett1/miniflux-feed-dedup

# busybox wget (present by default) is used for the healthcheck.
WORKDIR /app
COPY dedup.py /app/dedup.py

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD wget -qO- http://127.0.0.1:8090/healthz >/dev/null 2>&1 || exit 1

CMD ["python", "-u", "/app/dedup.py"]
