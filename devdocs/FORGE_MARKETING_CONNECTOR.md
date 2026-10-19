# ForgeMarketing suggested-todo connector

The personal dashboard is Yavin's canonical writable todo store. This connector
imports ForgeMarketing actions into `suggested_todos`; `yavin-home` can continue
to aggregate the dashboard instead of maintaining another task database.

ForgeMarketing remains authoritative. Imported suggestions are marked read-only,
keep the source UUID/version, preserve the approval requirement, and link back to
the canonical action and report. A locally rejected suggestion is never reopened.

## Run locally

Issue a dedicated `actions:read` consumer token, then provide it only through the
process environment:

```sh
export FORGE_MARKETING_URL="https://marketing.example.com"
export FORGE_MARKETING_TOKEN="<one-time-issued-token>"
python3 scripts/sync_forge_marketing.py
```

The database stores only the API URL, opaque checkpoint, timestamps, counts, and
the latest imported version for each source UUID. It never stores the token.
Checkpoint advancement and todo writes occur in the same SQLite transaction.

The command retries transient failures up to three times by default (maximum
five), uses bounded exponential backoff, and emits machine-readable JSON. Every
attempt is recorded in `connector_sync_runs`; health includes the most recent
status/error and consecutive failures. Token-shaped values are redacted. Set
`FORGE_MARKETING_SYNC_ATTEMPTS` to change the bounded attempt count.

HTTP 401/403 failures stop after the first attempt; rate limits, network errors,
and server failures remain retryable. A local task route can construct the
connector at click time and call `create_report_access_link()` with the stored
`report_access_endpoint`. The method enforces the configured ForgeMarketing
origin before sending authorization and returns a fresh expiring browser URL.

Scheduling should be enabled only after the endpoint is reachable and an
administrator can issue/revoke credentials. Status writeback is outside v1.
