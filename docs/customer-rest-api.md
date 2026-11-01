# Customer REST API

Use **`https://api.kavara.ai`** for customer REST calls from Python or curl.

- [OpenAPI specification](customer-rest-api.openapi.json)
- [Create an account or manage keys](https://kavara.ai/console)

Earlier preview routes are not part of the v1 customer API and are not supported.

Hosted MCP is a separate surface. See [Connect your Claude](connect-your-claude.md).
Do not send MCP calls to `api.kavara.ai`.

## Account and key

1. Sign in at [kavara.ai/login](https://kavara.ai/login) with Google or GitHub,
   open **API keys** in the [customer console](https://kavara.ai/console) and
   create a customer API key. Copy the key when it is shown and store it in
   your secret manager.
2. Inject the key as `KIP_API_KEY`. Do not commit it, put it in a URL, or paste
   it into a shared transcript.
3. Send exactly one `X-Kavara-Key` header on every request. A customer key has
   the form `k_` followed by 32 hex characters.
4. If your environment restricts outbound domains, allow HTTPS to `api.kavara.ai`.

A **snapshot** is the byte string returned by create. Learn and score send that
snapshot back with **samples**: `n` squares of `V` × `V`.

## Published operations

These are the operations in the published customer contract. A first session
checks the key (`health`) and the published limits (`contract`), then creates
a snapshot. Learn and score are in the same contract. Their body is an archive,
not JSON, so the copy-paste samples stop at create.

| Method | Path | Request | Success body |
| --- | --- | --- | --- |
| GET | `/v1/kirk-api/health` | None | JSON. `readiness` is `ready` |
| GET | `/v1/kirk-api/contract` | None | JSON limits, `outputs` and `rate_limit` |
| GET | `/v1/kirk-api/openapi.json` | None | This contract, as JSON |
| POST | `/v1/kirk-api/create` | JSON | Binary snapshot |
| POST | `/v1/kirk-api/learn` | `application/x-kirk-npz` | npz outputs and a new snapshot |
| POST | `/v1/kirk-api/score` | `application/x-kirk-npz` | npz outputs |

`create`, `learn` and `score` successes include `X-Kavara-Receipt`: `rcpt_`
and 32 hex characters, a new value on each call. Health, contract and errors
do not. Account responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`
and `X-RateLimit-Reset`.

The limit is 300 calls per account per fixed 60 second window, counting every
`/v1/kirk-api/*` call. The largest body is 8 MiB (8388608 bytes, 8 × 1024 × 1024).

### Python

Python 3 standard library only. Set `KIP_API_KEY` before starting. The script
does not retry. A create response is bytes; the script prints JSON bodies only.

```python
import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://api.kavara.ai"
API_KEY = os.environ["KIP_API_KEY"]


def call(method, path, payload=None):
    headers = {"X-Kavara-Key": API_KEY}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read()
            print(response.status, response.headers.get("Content-Type"))
            content_type = response.headers.get("Content-Type") or ""
            if content_type.startswith("application/json"):
                print(json.loads(raw.decode("utf-8")))
            return raw
    except urllib.error.HTTPError as error:
        print("HTTP", error.code, error.read().decode("utf-8", "replace"))
        raise SystemExit(1)


call("GET", "/v1/kirk-api/health")
call("GET", "/v1/kirk-api/contract")
call("POST", "/v1/kirk-api/create", {"hyperparameters": {"visible_nodes": 1}})
```

### curl

The same three calls, with the same headers and the same JSON body. `-o` writes each response body to a file.

```bash
set -eu
: "${KIP_API_KEY:?}"
BASE_URL="https://api.kavara.ai"

curl --silent --show-error --fail-with-body \
  --request GET \
  --url "${BASE_URL}/v1/kirk-api/health" \
  --header "X-Kavara-Key: ${KIP_API_KEY}" \
  -o health.json

curl --silent --show-error --fail-with-body \
  --request GET \
  --url "${BASE_URL}/v1/kirk-api/contract" \
  --header "X-Kavara-Key: ${KIP_API_KEY}" \
  -o contract.json

curl --silent --show-error --fail-with-body \
  --request POST \
  --url "${BASE_URL}/v1/kirk-api/create" \
  --header "X-Kavara-Key: ${KIP_API_KEY}" \
  --header "Content-Type: application/json" \
  --data '{"hyperparameters":{"visible_nodes":1}}' \
  -o snapshot.bin
```

## Response excerpts

From the contract schema, not from a live capture.

Health returns `200` and JSON. `readiness` is required. `release_id`, when
present, is a string.

```json
{"readiness": "ready"}
```

Contract returns `200` and JSON. These fields are fixed by the schema. The
response may also include `release_id`, `api_version`, `max_batch` and
`snapshot_binding` (`required` or `off`).

```json
{
  "readiness": "ready",
  "max_body_bytes": 8388608,
  "outputs": ["all", "entropy", "features"],
  "rate_limit": {
    "per_account_per_minute": 300,
    "window": "fixed",
    "window_seconds": 60,
    "scope": "every /v1/kirk-api/* call by one account",
    "headers": [
      "X-RateLimit-Limit",
      "X-RateLimit-Remaining",
      "X-RateLimit-Reset",
      "Retry-After"
    ]
  }
}
```

Create returns `200` and the snapshot bytes. `Content-Type` is
`application/octet-stream`, or `application/x-kirk-npz` with members
`snapshot` and `snapshot_envelope` when `snapshot_binding` is `required`.
Keep `X-Kavara-Receipt` with the snapshot. The body is not a JSON object.

The create body in the samples is the smallest object the schema accepts:
`hyperparameters.visible_nodes` is an integer of at least 1. `random_state`
is an optional integer. `Content-Type` is `application/json`.

```json
{"hyperparameters": {"visible_nodes": 1}}
```

## Learn and score

`POST /v1/kirk-api/learn` and `POST /v1/kirk-api/score` take
`Content-Type: application/x-kirk-npz` (no pickle). The archive holds:

- `snapshot`: uint8 bytes from create, or from a previous learn
- `samples`: `n` squares of `V` × `V`, dtype float32, float64, complex64 or
  complex128, every real and imaginary part in [-1, 1]

Optional query `outputs` is one of `all` (the default), `entropy` or
`features`. Any other value is `422` with `{"error":"invalid_outputs"}`.

A success is `application/x-kirk-npz`:

| `outputs` | Members |
| --- | --- |
| `all` | `entropy` float32 `(n,)`, `feature_arr` complex64 `(n, V, V)`, `feature_vec` complex64 `(n, 2V)`, `feature_scalar` complex64 `(n,)` |
| `entropy` | `entropy` only |
| `features` | `feature_arr`, `feature_vec`, `feature_scalar` |

Learn also returns `snapshot` (uint8). Score does not. Both successes include
`X-Kavara-Receipt`. Build the archive from the create response before sending
it. The samples above do not invent archive bytes.

## Errors

Bodies below are the contract's error objects.

| HTTP | Body | When |
| --- | --- | --- |
| 401 | `{"error":"invalid_api_key"}` | No key, a repeated key header, or a key that is not `k_` plus 32 hex |
| 403 | `{"error":"request_denied"}` | Unknown key, revoked key, or a key with no tenant row. One body for all three |
| 404 | `{"error":"route_not_found"}` | Unknown path or method |
| 413 | `{"error":"request_too_large"}` | Body over 8 MiB (8388608 bytes) |
| 415 | `{"error":"unsupported_content_type"}` | Not `application/json` on create, or not `application/x-kirk-npz` on learn and score |
| 422 | `{"error":"invalid_outputs"}` | `outputs` is not `all`, `entropy` or `features` |
| 422 | `EnvelopeRefused` | `error` is `EnvelopeRefused`, with `rule` (`input_range` or `chain_length`) and `message`. `input_range` means a part was outside [-1, 1] |
| 400 or 409 | `{"error":"invalid_request"}` | The service refused the archive or another input |
| 429 | `{"error":"rate_limited","retry_after":N}` | Over 300 calls in the window. `Retry-After` equals `N` |
| 402 | `{"error":"insufficient_credits"}` | Reserved for a credit check |
| 500, 502 or 503 | `{"error":"origin_unavailable"}` | The service could not return an answer |
| 503 | `{"error":"receipt_unavailable"}` | A receipt row could not be written. No output is returned |

A rate-limit body matches this shape. `retry_after` is an integer from 1 to 60.

```json
{"error": "rate_limited", "retry_after": 1}
```

Some paths the contract does not define answer `404` or `405` with a JSON
object of only `code` and `message`. A response from this API for an unknown
route is `{"error":"route_not_found"}`.

A finished check is HTTP 200 from health, HTTP 200 from contract, and HTTP 200
from create with a receipt header. A reachable login page alone does not
establish API access.
