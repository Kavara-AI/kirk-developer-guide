# Connect your Claude

This page covers the connector that puts the Kirk MCP tools directly into a
Claude conversation. Hosted MCP (`https://kirk-mcp.kavara.ai/mcp`) can also
be called directly from code. For REST calls from code, Postman or an agent,
use the [Customer REST API](customer-rest-api.md). For which calls need a key,
and how a refusal is returned, see the [MCP auth contract](mcp-auth-contract.md).

## What you need

A customer API key. Key creation is self-service: sign in at
[kavara.ai/login](https://kavara.ai/login) with Google or GitHub, open **API keys**
in the [console](https://kavara.ai/console) and create a key. The key is bound to
your Kavara account.

Send the key against the bare `/mcp` path. The
[auth contract](mcp-auth-contract.md) is the rule for the handshake, the demo
tools, and a bad key.

- **Header** — `Authorization: Bearer k_...`. `X-Kirk-Key: k_...` is the same
  check. This is the supported route.
- **Legacy URL** — a key in the path or query string is still accepted for
  existing clients, and it is deprecated. Do not put a key in a URL for a new
  client. If a URL key and a header are both present, the URL key wins.
- **Cloudflare Access service token** — a client id and secret, used against the
  bare `/mcp` path. Kavara issues these.

A key can spend real balance on metered tools, so treat it as a secret: do not
commit it, paste it into an issue, or share it in chat.

## Claude Code

Pass the key as a header:

```sh
claude mcp add --transport http kirk https://kirk-mcp.kavara.ai/mcp \
  -H "Authorization: Bearer <key>"
```

Confirm with `claude mcp list`.

## Claude Desktop and claude.ai

Add the connector at `https://kirk-mcp.kavara.ai/mcp`. Do not put a key in a
connector URL.

Some organizations have a Request headers section in the Add custom connector
dialog. This is a beta. If that section is there, choose the header
`authorization`, set sign-in to **No sign-in**, and enter the value as
`Bearer k_...`. Claude sends the value as entered and does not add a scheme.
On Team and Enterprise plans, only an Owner adds the org connector. Every
member's metered calls spend that one Kavara account's balance. Use a
dedicated, revocable key for the org connector.

If the dialog has no Request headers section, the organization does not have
this beta. Use Claude Code with the header form above.

Anthropic describes the dialog in
[Add a connector by URL](https://claude.com/docs/connectors/custom/remote-mcp)
(also published as
[add an unlisted connector](https://claude.com/docs/connectors/custom/add-unlisted))
and in
[Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Check it worked

Ask Claude to run `kirk_list_models`. A working connection returns the
registered model ids.

## Free and metered tools

Start with the free ones — they cost nothing and answer most orientation
questions.

| Tool | Cost | What it does |
| --- | --- | --- |
| `kirk_list_models` | 0 IU | registered model ids |
| `kirk_render_book` | 0 IU | inspect the rendered tensor without scoring |
| `kirk_bulk_howto` | 0 IU | returns a stdlib Python client for bulk work |
| `kirk_billing_show` / `kirk_billing_usage` | 0 IU | balance and usage |
| `kirk_score_book` | 1 IU per call | score one snapshot |
| `kirk_score_book_batch` | 1 IU per 50 books | score many independent snapshots |
| `kirk_score_l2_book` | 1 IU per call | score full L2 books as one ordered chain |

These book tools are fixed routes. Kirk's general input is one square matrix
per step, which you build; see [tensor generation](tensor-generation.md).

Every response carries a `_cost` envelope, so a client can account for spend
without inferring it. The connector also ships its own usage policy in its
instructions — read that before calling the metered tools.

## Do not loop the scoring tools from a chat

Above roughly 200 books, call `kirk_bulk_howto`. It returns a self-contained
Python client that scores with zero model tokens per book. Both scoring tools
are capped by design, and driving them in a per-book loop from a chat model is
the expensive way to do the same work.

## Troubleshooting

- **A 403 that looks like an authentication failure.** Often it is the
  `User-Agent`: Cloudflare rejects some default client agents on this zone with
  a 1010 "browser signature banned" error that surfaces as a 403. Set an
  explicit `User-Agent` before debugging credentials.
- **A 402.** The account balance is exhausted. `kirk_billing_show` confirms it.
- **A key that stops working.** Keys can be revoked. An unknown or revoked key
  is refused outright rather than being silently downgraded to an
  unattributed account, so this surfaces as a hard failure, not as odd
  behaviour. Where it surfaces depends on the call. On `tools/list`, a bad key
  fails the listing, so a connector can fail during discovery with no tool
  result to inspect. On a tool call, the observed refusal is a tool result with
  `isError` set. The key check does not send HTTP 401; see the
  [auth contract](mcp-auth-contract.md). Create a new key in the
  [console](https://kavara.ai/console). Each key belongs to one account. On the
  org connector, members share that one stored key, and their calls spend that
  account's balance.
- **A model appears in `kirk_list_models` but errors when called.** The
  catalogue lists registered models; it is not a liveness check. Report it
  rather than assuming the call was malformed.

## Next

- [Start Here](../START_HERE.md) for the reading order.
- [Tensor generation](tensor-generation.md) for the input contract.
- [Benchmark 001](../benchmarks/benchmark-001-l2-order-book/README.md) for the
  first practical test.
