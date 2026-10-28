# Customer REST API

Use **`https://api.kavara.ai`** for customer REST calls from Python, curl,
Postman or an agent with HTTPS access. No Claude connector is required.

- [OpenAPI specification](customer-rest-api.openapi.json)
- [Create an account or manage keys](https://kavara.ai/console)
- [Download the Postman starter](https://kavara.ai/console/downloads/Kirk-Engineer-Starter.zip)

**Observed — 2 October 2026:** a customer account completed a model-list
request through this hostname in Postman. It returned HTTP 200. This is
bounded customer-access validation, not a throughput, latency or scale guarantee.

## Choose REST or MCP

| Surface | Endpoint | Contract |
| --- | --- | --- |
| Customer REST | `https://api.kavara.ai` | The routes below, JSON bodies and `X-Kavara-Key` |
| Hosted MCP | `https://kirk-mcp.kavara.ai/mcp` | MCP JSON-RPC tools; see [Connect your Claude](connect-your-claude.md) for its credential header and current tool policy |

Both use HTTPS. MCP is also callable directly from code; it does not require
Claude. These surfaces have different contracts. Do not send MCP JSON-RPC to
`api.kavara.ai` or assume REST routes exist beneath the MCP URL.

The REST service does not expose arbitrary file upload, tensor rendering, batch
scoring, billing or MCP routes. The general input contract — one square matrix
per step, built by you — is described in [tensor generation](tensor-generation.md).
For other data, start with the [agent intake workflow](agent-guide.md).

## Account, key and network access

1. Sign in at [kavara.ai/login](https://kavara.ai/login) with Google or GitHub,
   open **API keys** in the [customer console](https://kavara.ai/console) and
   create a customer API key. Console keys have fixed read-and-score access, so
   there is nothing to enable. Keys are self-service and bound to your account;
   copy the key when it is shown and store it in your secret manager.
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

For an agent, use a separate customer key and revoke it when no longer needed.
Availability of a credential does not authorize unrelated workloads or spending.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/models` | Read available models and select a compatible model ID |
| POST | `/v1/score-book` | Unavailable: this route is no longer offered. |

Do not append query strings. Successful responses have the envelope
`{"result": ...}`. Keep the returned field names and raw result; model-specific
output is not a universal response schema.

### Fastest path: Postman

Download and unzip the [starter](https://kavara.ai/console/downloads/Kirk-Engineer-Starter.zip).
Import both the collection and environment JSON files, select **Kirk — My access**,
and set `api_key` through a local, unshared secret value or Postman Vault. The
shipped environment contains no key. Do not publish or sync customer credentials.

Run the list-models request.

### Python

This uses Python 3's standard library. Inject `KIRK_API_KEY` before starting;
there is no credential in the script. Use synthetic data first.

```python
import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://api.kavara.ai"
API_KEY = os.environ["KIRK_API_KEY"]


def call(path):
    headers = {"X-Kavara-Key": API_KEY, "Accept": "application/json"}
    request = urllib.request.Request(BASE_URL + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            result = json.load(response)
            print(response.status, response.headers.get("X-Request-Id"), result)
            return result
    except urllib.error.HTTPError as error:
        # Report identifiers for support; never print request headers or keys.
        print("HTTP", error.code, "request", error.headers.get("X-Request-Id"))
        raise SystemExit(1)


call("/v1/models")
```

Scoring is not available through this API.

The current customer data-fit path records zero credits. Paid ongoing workflow
activation is separate; this does not establish pricing for MCP scoring or other
contracts. Check current account policy before extending the workload.

## Errors and completion checks

The adapter returns JSON errors as `{"error": "code"}`:

| HTTP | Code | Check |
| --- | --- | --- |
| 400 | `invalid_headers` | Missing or duplicated key header, or invalid header framing |
| 401 | `invalid_api_key` | Key format |
| 402 | `insufficient_credits` | Account allowance for the requested operation |
| 403 | `request_denied` | Key/account validity and required permissions |
| 404 | `route_not_found` | Exact method/path, no query string |
| 429 | `rate_limited` | Reduce request rate |
| 502 / 503 | `origin_unavailable` | Service availability; report request ID to support |

Adapter responses include `Cache-Control: no-store` and `X-Request-Id`.
Errors generated earlier by infrastructure can have a different envelope.
For support, retain status, request ID and a redacted input description, never the
key. A successful setup has a real HTTP 200 from model listing, with the
response and its request ID retained. A reachable login page or imported
collection alone does not establish working API access.
