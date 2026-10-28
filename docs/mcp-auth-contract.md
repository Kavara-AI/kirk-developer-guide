# MCP auth contract

This page states which calls on the hosted Kirk MCP server need an account
key, where that key is sent, and how a refusal is returned.

The server is `https://kirk-mcp.kavara.ai/mcp`. Customer REST at
`https://api.kavara.ai` is a separate contract: it uses `X-Kavara-Key`, and
an `Authorization` header alone does not authenticate those routes. See
[Customer REST API](customer-rest-api.md).

The behaviour below was verified against the Kavara account service as of
17 October 2026. Where a live call is cited, it is labelled
**Observed**.

## Terms

An **account key** is the secret Kavara issues for an account. Send it in
the header below. Do not commit it, paste it into an issue, or put it in a
URL.

A **tool call** is an MCP `tools/call` for one named tool. The **handshake**
is `initialize` and `tools/list`.

## Handshake

`initialize` and `tools/list` need no key.

The server is built without an authentication provider on the protocol
session. The key middleware forwards an `/mcp` request that contains no key,
and it does not stop the request before the protocol handler runs.
`initialize` does not resolve the key, so a caller who sends nothing still
completes the handshake.

`tools/list` does resolve identity, so it can omit tools that are not public.
A missing key does not fail that listing. A key that is unknown, revoked, or
expired does: list handling raises, and the listing is not returned.

## Where to send the key

The supported route is a header on `https://kirk-mcp.kavara.ai/mcp`:

- `Authorization: Bearer <key>`
- `X-Kirk-Key: <key>`

Both headers are read by the same check. Use `Authorization` when the client
can set a header.

A key in the path (`/mcp/<key>`) or the query string (`k` or `key`) is still
accepted on this revision. That form is legacy, and it is deprecated for a
new client. When more than one form is present, the first match wins, in
this order: path, then query, then header. A leftover path or query key
overrides the header.

The server first decides whether a header value is a candidate account key.
A value that is not a candidate, including an unrelated `Authorization`
scheme, is ignored. The request continues as a request with no key, and it
is not reported as an unknown key. A value that is a candidate but matches no
live key is an unknown key, and it is refused; see the next section. A
mistyped key can land on either side: if it no longer reads as a candidate,
the call runs with no key; if it still does, the call is refused.

## Unknown, revoked, or disallowed key

A key that is present and unknown, revoked, or expired stops resolution. The
call is refused. It is not attributed to any other account.

A key that resolves, but is not allowed to perform the operation, is refused
at the entitlement check. That refusal stays on the same account.

The check runs on `tools/list` and on every tool call, including the two
demo tools below. Sending a bad key is a different event from sending no key.

## Calls with no key

Sending no key does not fail the key check. Later checks still apply, and
they differ by tool.

### Demo tools

`kirk_demo_trading` and `kirk_demo_uav` are public, cost 0, and are
rate-limited to 3 calls per hour per client address. The rate card describes
them as first-touch validation for unauthenticated callers. The server
instructions tell a first-time caller to run them with no credentials.

**Current behaviour, under review.** This is what that revision does. It is
an open question whether these two tools stay callable with no key. Do not
treat the open demo as a stable interface.

A bad key on either demo is still the hard refusal above. "No credentials"
means the request carries no key.

### Charged tools

These tools have a positive cost: `kirk_infer_legacy`, `kirk_score_book`,
`kirk_score_l2_book`, `kirk_score_book_batch`, and `kirk_score_random`.
`kirk_score_book_batch` costs 1 per 50 books, with a minimum of 1.

The balance check runs before the tool body. The call runs when the resolved
account can cover that cost. Send a valid account key so the call is
attributed to your account. A missing key does not attribute the call to a
customer account.

On a managed account, the key must also allow the operation. A scored call
additionally requires the execution headers named in the server instructions,
`X-Kavara-Workflow` and `Idempotency-Key`. Those headers do not replace the
account key.

### Other zero-cost tools

`kirk_list_models`, `kirk_render_book`,
`kirk_bulk_howto`, and the `kirk_billing_*` tools are priced at 0, so the
balance check does not stop them. This revision has no separate "key
required" gate for them. Send your own key when the result has to be
attributed to your account. A billing read reports the account the call
resolved to.

### Tools that are not public

A tool that is not public is omitted from `tools/list` unless the resolved
account is on an operator allowlist. A direct call by name is refused for
every other account, with the same error shape as a tool that is not
registered. Holding a valid customer key does not by itself place an account
on that list.

## How a refusal is returned

The key check raises inside list handling or tool handling. That path does
not send HTTP 401.

**Observed** (11 October 2026, hosted MCP): a revoked key on a tool call was
refused as a tool result with `isError` set. The same shape was returned for
a path key, a query key, `Authorization: Bearer`, and `X-Kirk-Key`.
`initialize` still completed for a caller who sent no key. That run is not
stored in this repository. Clients should read the tool result.

## Related

- [Connect your Claude](connect-your-claude.md) for the connector commands.
- [Customer REST API](customer-rest-api.md) for the separate REST host and
  header.
