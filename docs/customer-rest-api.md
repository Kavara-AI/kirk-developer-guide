# Customer REST API

Use **`https://api.kavara.ai`** for customer REST calls from Python, curl,
Postman or an agent with HTTPS access. No Claude connector is required.

- [OpenAPI specification](customer-rest-api.openapi.json)
- [Create an account or manage keys](https://kavara.ai/console)
- [Download the Postman starter](https://kavara.ai/console/downloads/Kirk-Engineer-Starter.zip)

**Observed — 2 October 2026:** a customer account completed engine, model-list and
single-book score requests through this hostname in Postman. All three returned
HTTP 200; account receipts recorded zero credits for this data-fit path. This is
bounded customer-access validation, not a throughput, latency or scale guarantee.

## Choose REST or MCP

| Surface | Endpoint | Contract |
| --- | --- | --- |
| Customer REST | `https://api.kavara.ai` | The three routes below, JSON bodies and `X-Kavara-Key` |
| Hosted MCP | `https://kirk-mcp.kavara.ai/mcp` | MCP JSON-RPC tools; see the [MCP quickstart](../examples/quickstart/README.md) for its credentials and current tool policy |

Both use HTTPS. MCP is also callable directly from code; it does not require
Claude. These surfaces have different contracts. Do not send MCP JSON-RPC to
`api.kavara.ai` or assume REST routes exist beneath the MCP URL.

The REST service currently admits a fixed, ten-level price-book input. It does
not expose arbitrary file upload, tensor rendering, batch scoring, billing or
MCP routes. For other data, start with the [agent intake workflow](agent-guide.md).

## Account, key and network access

1. Sign in at the [customer console](https://kavara.ai/console), create a customer
   API key and enable the read and score permissions needed for this example.
2. Supply the key through your client's secret controls. For code, inject it as
   `KIRK_API_KEY` through your environment's secret manager. Do not commit it, put
   it in a URL, or paste it into a shared transcript. Sandbox capabilities vary;
   chat is not the only possible way to supply a credential.
3. Send exactly one `X-Kavara-Key` header on every request. A customer key has the
   form `k_` followed by 32 lowercase hexadecimal characters. An
   `Authorization: Bearer ...` header alone does not authenticate these routes.
   Customer REST calls do not require Cloudflare service credentials.
4. If your environment restricts outbound domains, have its administrator allow
   HTTPS to `api.kavara.ai`. Allow `kavara.ai` for account access or downloading the
   starter. Add `kirk-mcp.kavara.ai` only if using the separate MCP surface.

For an agent, use a separate customer key with the required scopes and revoke it
when no longer needed. Availability of a credential does not authorize unrelated
workloads or spending.

## Three supported calls

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/engine` | Read engine identity; retain its returned SHA with results |
| GET | `/v1/models` | Read available models and select a compatible model ID |
| POST | `/v1/score-book` | Score one ten-level bid/ask price book |

Do not append query strings. Successful responses have the envelope
`{"result": ...}`. Keep the returned field names and raw result; model-specific
output is not a universal response schema.

### Fastest path: Postman

Download and unzip the [starter](https://kavara.ai/console/downloads/Kirk-Engineer-Starter.zip).
Import both the collection and environment JSON files, select **Kirk — My access**,
and set `api_key` through a local, unshared secret value or Postman Vault. The
shipped environment contains no key. Do not publish or sync customer credentials.

Run **1. Verify engine**, then **2. List models**, then **3. Score example book**. Confirm the configured
`model_id` is available before scoring. The starter generates a fresh UUID for
each score send; for a retry of the same logical operation, retain and reuse the
original UUID instead.

### Python: the same three calls

This uses Python 3's standard library. Inject `KIRK_API_KEY` before starting;
there is no credential in the script. Use synthetic data first.

```python
import json
import os
import urllib.error
import urllib.request
import uuid

BASE_URL = "https://api.kavara.ai"
API_KEY = os.environ["KIRK_API_KEY"]


def call(path, payload=None, request_id=None):
    headers = {"X-Kavara-Key": API_KEY, "Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["Idempotency-Key"] = request_id
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(BASE_URL + path, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            result = json.load(response)
            print(response.status, response.headers.get("X-Request-Id"), result)
            return result
    except urllib.error.HTTPError as error:
        # Report identifiers for support; never print request headers or keys.
        print("HTTP", error.code, "request", error.headers.get("X-Request-Id"))
        raise SystemExit(1)


call("/v1/engine")
call("/v1/models")
# Choose a compatible model from the returned catalog before scoring.
model_id = input("Available compatible model ID: ").strip()
score_id = str(uuid.uuid4())
print("Retain this score Idempotency-Key for any retry:", score_id)
call("/v1/score-book", {
    "bid_px": [99.99, 99.98, 99.97, 99.96, 99.95, 99.94, 99.93, 99.92, 99.91, 99.90],
    "ask_px": [100.01, 100.02, 100.03, 100.04, 100.05, 100.06, 100.07, 100.08, 100.09, 100.10],
    "model_id": model_id,
}, request_id=score_id)
```

The starter's example model is `kirk-test1-binary-threshold-v1`; use it only while
it remains available and compatible. An unattended agent should read the model
catalog and configure the compatible model explicitly instead of using `input()`.
The script does not retry automatically.

## Score input and retries

The JSON object must contain **exactly** `bid_px`, `ask_px` and `model_id`.
Each price array must contain exactly ten finite, positive JSON numbers;
strings and booleans are invalid. Send level 1 first: descending bids and ascending
asks, with the best bid below the best ask, as in the synthetic example.
`model_id` must match `[a-z0-9][a-z0-9_-]{0,127}` and name an available model.
The maximum request body is 256 KiB. Use `Content-Type: application/json`.

Every score POST requires **`Idempotency-Key`**, a canonical lowercase UUID v4.
Generate one for each new logical score. If a response is lost, retain that UUID
and the identical body for any retry; do not turn an uncertain request into a new
operation. Do not send `Idempotency-Key` on either GET route: it is rejected.

The current customer data-fit path records zero credits. Paid ongoing workflow
activation is separate; this does not establish pricing for MCP scoring or other
contracts. Check current account policy before extending the workload.

## Errors and completion checks

The adapter returns JSON errors as `{"error": "code"}`:

| HTTP | Code | Check |
| --- | --- | --- |
| 400 | `invalid_headers` | Missing or duplicated key header, or invalid header framing |
| 400 | `missing_idempotency_key` / `invalid_idempotency_key` | UUID v4 on POST only |
| 400 | `invalid_json` / `invalid_request` | JSON syntax, exact fields, dimensions and value types |
| 401 | `invalid_api_key` | Key format |
| 402 | `insufficient_credits` | Account allowance for the requested operation |
| 403 | `request_denied` | Key/account validity and required permissions |
| 404 | `route_not_found` / `model_not_found` | Exact method/path, no query string, available model |
| 413 | `request_too_large` | Body size and content length |
| 429 | `rate_limited` | Reduce request rate; retain score operation identity for retries |
| 502 / 503 | `origin_unavailable` | Service availability; report request ID to support |

Adapter responses include `Cache-Control: no-store` and `X-Request-Id`.
Errors generated earlier by infrastructure can have a different envelope.
For support, retain status, request ID and a redacted input description, never the
key. A successful setup has three real HTTP 200 responses, engine/model identity
and a retained score result. A reachable login page or imported collection alone
does not establish working API access.
