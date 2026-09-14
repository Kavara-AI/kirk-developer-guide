# Connect your Claude

There are two ways to reach Kirk: a Python client, or a connector that puts the
Kirk tools directly into a Claude conversation. This page covers the connector.
For the client, see the [quickstart](../examples/quickstart/README.md).

## What you need

A credential, in one of two forms:

- **Personal connector URL** — `https://kirk-mcp.kavara.ai/mcp/k_...`. Carries
  its own authentication, so no headers are needed.
- **Cloudflare Access service token** — a client id and secret, used against the
  bare `/mcp` path.

Kavara issues these. Either form spends real balance, so treat it as a secret:
do not commit it, paste it into an issue, or share it in chat.

## Claude Code

With a connector URL:

```sh
claude mcp add --transport http kirk 'https://kirk-mcp.kavara.ai/mcp/k_...'
```

With a service token:

```sh
claude mcp add --transport http kirk https://kirk-mcp.kavara.ai/mcp \
  -H "CF-Access-Client-Id: ..." \
  -H "CF-Access-Client-Secret: ..."
```

Confirm with `claude mcp list`.

## Claude Desktop and claude.ai

Settings → Connectors → Add custom connector, then paste the connector URL. A
connector URL is the simpler form here because it authenticates on its own.

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

Every response carries a `_cost` envelope, so a client can account for spend
without inferring it. The connector also ships its own usage policy in its
instructions — read that before calling the metered tools.

## Do not loop the scoring tools from a chat

Above roughly 200 books, call `kirk_bulk_howto`. It returns a self-contained
Python client that scores with zero model tokens per book. Both scoring tools
are capped by design, and driving them in a per-book loop from a chat model is
the expensive way to do the same work.

## If you also write scripts: one naming trap

The same credential appears under different environment-variable names
depending on which client you started from:

| Source | Variables |
| --- | --- |
| [quickstart](../examples/quickstart/README.md) | `KIRK_CF_CLIENT_ID`, `KIRK_CF_CLIENT_SECRET` |
| client returned by `kirk_bulk_howto` | `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` |

`KIRK_MCP_URL` means the same thing in both. If you move between the two and
authentication starts failing, check the variable names before the credential.

## Troubleshooting

- **A 403 that looks like an authentication failure.** Often it is the
  `User-Agent`: Cloudflare rejects some default client agents on this zone with
  a 1010 "browser signature banned" error that surfaces as a 403. Set an
  explicit `User-Agent` before debugging credentials.
- **A 402.** The account balance is exhausted. `kirk_billing_show` confirms it.
- **A model appears in `kirk_list_models` but errors when called.** The
  catalogue lists registered models; it is not a liveness check. Report it
  rather than assuming the call was malformed.

## Next

- [Start Here](../START_HERE.md) for the reading order.
- [Tensor generation](tensor-generation.md) for what the engine expects.
- [Benchmark 001](../benchmarks/benchmark-001-l2-order-book/README.md) for the
  first practical test.
