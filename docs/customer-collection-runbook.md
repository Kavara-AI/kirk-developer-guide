# Customer collection runbook

**Draft.** This page is a draft procedure for a customer-safe API collection.
It is not a published contract, and it does not record a live run.

Use it with the [Customer REST API](customer-rest-api.md) and the
[OpenAPI specification](customer-rest-api.openapi.json). Those pages remain the
contract. This runbook only says how to keep a collection safe to store.

## Placeholders

The collection stores placeholders. Fill them in the client's secret control
or a local unshared environment. Do not commit filled-in values, sync them,
or paste them into a shared transcript.

| Placeholder | Use |
| --- | --- |
| `{{base_url}}` | API origin, supplied outside the collection |
| `{{api_key}}` | Customer key, supplied outside the collection |

## Header key

Send exactly one authentication header on every request:

```http
X-Kavara-Key: {{api_key}}
Accept: application/json
```

An `Authorization` header alone does not authenticate these routes.

## Call the model catalog

1. Set `{{base_url}}` and `{{api_key}}` outside the collection file.
2. Send `GET {{base_url}}/v1/models` with the header above. Do not append a query string.
3. Read the `result` object. Fields inside `result` are TBD. Engine and identity
   fields are not part of the contract.

Customer identity `release_id` comes with the next API release and is not part
of this response today.

## Completion

**Expected:** a stored collection that authenticates with `X-Kavara-Key`, uses
placeholders, and reads `GET /v1/models`. A downloaded file alone is not a
completed call.
