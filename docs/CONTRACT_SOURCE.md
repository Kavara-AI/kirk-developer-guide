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

`max_body_bytes` is 8 MiB (8388608, which is 8 × 1024 × 1024).

## Sync

CI for this repository cannot read the account service repo, so the workflow
does not fetch the upstream file and does not store a credential for it.

Someone who can already read that repo runs:

    python3 scripts/sync_customer_contract.py

The script reads `contracts/kirk-api/openapi.customer.json` on `main` with the
caller's existing `gh` login. It compares that document with the vendored
spec and does not write either file. If the login cannot see the repo, the
script says so and exits.
