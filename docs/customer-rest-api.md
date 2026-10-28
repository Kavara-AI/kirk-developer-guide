# Customer REST API

Use **`https://api.kavara.ai`** for customer REST calls from Python, curl,
Postman or an agent with HTTPS access. No Claude connector is required.

- [OpenAPI specification](customer-rest-api.openapi.json)
- [Create an account or manage keys](https://kavara.ai/console)

## Choose REST or MCP

| Surface | Endpoint | Contract |
| --- | --- | --- |
| Customer REST | `https://api.kavara.ai` | The route below, JSON bodies and `X-Kavara-Key` |
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
   HTTPS to `api.kavara.ai`. Allow `kavara.ai` for account access.
   Add `kirk-mcp.kavara.ai` only if using the separate MCP surface.

For an agent, use a separate customer key and revoke it when no longer needed.
Availability of a credential does not authorize unrelated workloads or spending.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/score-book` | Unavailable: this route is no longer offered. |

Do not append query strings. Successful responses have the envelope
`{"result": ...}`. Keep the returned field names and raw result; model-specific
output is not a universal response schema.

Scoring is not available through this API.

Paid ongoing workflow activation is separate. This page does not establish
pricing for MCP scoring or other contracts. Check current account policy
before extending the workload.

## Errors and completion checks

The adapter returns JSON errors as `{"error": "code"}`:

| HTTP | Code | Check |
| --- | --- | --- |
| 400 | `invalid_headers` | Missing or duplicated key header, or invalid header framing |
| 401 | `invalid_api_key` | Key format |
| 403 | `request_denied` | Key/account validity and required permissions |
| 404 | `route_not_found` | Exact method/path, no query string |
| 429 | `rate_limited` | Reduce request rate |
| 502 / 503 | `origin_unavailable` | Service availability; report request ID to support |

Adapter responses include `Cache-Control: no-store` and `X-Request-Id`.
Errors generated earlier by infrastructure can have a different envelope.
For support, retain status, request ID and a redacted input description, never the
key. A reachable login page or imported collection alone
does not establish working API access.
