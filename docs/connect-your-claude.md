# Connect your Claude

This page covers the connector that puts the Kirk MCP tools directly into a
Claude conversation. For calls from code, Postman or an agent, use the
[Customer REST API](customer-rest-api.md).

## What you need

A customer API key. Key creation is self-service: sign in at
[kavara.ai/login](https://kavara.ai/login) with Google or GitHub, open **API keys**
in the [console](https://kavara.ai/console) and create a key. The key is bound to
your Kavara account. Present it as a header (`Authorization: Bearer k_...`)
against the bare `/mcp` path. Never put a key in a URL.

A key can spend real balance on metered tools, so treat it as a secret: do not
commit it, paste it into an issue, or share it in chat.

## Claude Code

Pass the key as a header:

```sh
claude mcp add --transport http kirk https://kirk-mcp.kavara.ai/mcp \
  -H "Authorization: Bearer k_..."
```

Confirm with `claude mcp list`.

## Claude Desktop and claude.ai

These interfaces add custom connectors by URL only and cannot send a key
header. Do not put a key in a connector URL. Use Claude Code with the header
form above until an account sign-in (OAuth) connection is available.

## Check it worked

Ask Claude to run `kirk_verify_engine`. A working connection returns
`status: ok` and a `kirk_version` sha.

**Record that sha.** Results from different engine builds are not
interchangeable, and a result kept without its `kirk_version` cannot be placed
in a lineage afterwards.

## Free and metered tools

Start with the free ones — they cost nothing and answer most orientation
questions.

| Tool | Cost | What it does |
| --- | --- | --- |
| `kirk_verify_engine` | 0 IU | engine identity and sha |
| `kirk_list_models` | 0 IU | registered model ids and their engines |
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
  behaviour. Create a new key in the [console](https://kavara.ai/console); keys are per-account and are not shared.
- **A model appears in `kirk_list_models` but errors when called.** The
  catalogue lists registered models; it is not a liveness check. Report it
  rather than assuming the call was malformed.

## Next

- [Start Here](../START_HERE.md) for the reading order.
- [Tensor generation](tensor-generation.md) for the input contract.
- [Benchmark 001](../benchmarks/benchmark-001-l2-order-book/README.md) for the
  first practical test.
