# Quickstart

Three calls against the live Kirk MCP endpoint. All are **0 IU** — nothing here
scores, so the script can be run as often as you like while wiring up a client.

## Run it

```sh
export KIRK_CF_CLIENT_ID=...
export KIRK_CF_CLIENT_SECRET=...
python3 kirk_quickstart.py
```

Or point `KIRK_MCP_URL` at a personal connector URL and omit the headers.

Standard library only. Python 3.8+.

## What it shows

```text
engine   kirk-ed-2  sha f3c548477d3b5c76...
models   [{'id': ..., 'kind': ..., 'description': ...}, ...]
tensor   shape=[20, 20] dtype=complex128 non_zero=50 mid=223.095
cost     0 IU this session (all three are free)
```

Three things worth taking from that output:

1. **Record the engine sha.** Results from different engine builds are not
   interchangeable. A result kept without its `kirk_version` cannot be placed in a
   lineage afterwards.
2. **The engine builds the tensor.** You send 10 bid and 10 ask prices, level 1
   first; the 20 x 20 complex128 rendering happens engine-side. See
   [tensor generation](../../docs/tensor-generation.md).
3. **Cost is reported per call.** Every response carries a `_cost` envelope, so a
   client can account for spend without inferring it.

## One integration note

The script sets an explicit `User-Agent`. Cloudflare rejects Python's default on this
zone with a 1010 "browser signature banned" error, which arrives as a **403 that looks
like an authentication failure and is not one**. If you write your own client, set a
User-Agent before you start debugging credentials.

## Next

`kirk_score_book` and `kirk_score_book_batch` are metered. Read the usage policy in
the connector's own instructions before calling them, and use `kirk_bulk_howto` for
anything above 200 books.
