# Contract source

The vendored spec `customer-rest-api.openapi.json` is the customer contract
from the account service repo.

Synced 31 October 2026.

Operations kept:

- `GET /v1/kirk-api/health`
- `GET /v1/kirk-api/contract`
- `GET /v1/kirk-api/openapi.json`
- `POST /v1/kirk-api/create`
- `POST /v1/kirk-api/learn`
- `POST /v1/kirk-api/score`

`max_body_bytes` is 8 MiB (8 × 1024 × 1024).

## Digest

Each CI run hashes the whole vendored document: one JSON object, keys sorted,
compact separators, SHA-256. The digest is plain hex at
`scripts/customer-spec.digest`, the one path exempt from the hex scan. If the
vendored file is missing, is not JSON, or does not match that digest, the
step stops with an error and does not raise a traceback.

## Sync

CI cannot read the upstream repo and does not store a credential for it.
A person who can read it passes the upstream location as an argument, or
sets `KDG_UPSTREAM_SPEC`, and runs:

    python3 scripts/sync_customer_contract.py

The script compares servers, paths, methods, request and response schemas,
and security. It ignores descriptions and examples. It does not write files.
