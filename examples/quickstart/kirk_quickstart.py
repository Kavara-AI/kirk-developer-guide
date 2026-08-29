#!/usr/bin/env python3
"""Kirk MCP quickstart — three free calls, no scoring, no cost.

Exercises kirk_verify_engine, kirk_list_models and kirk_render_book. All three
are 0 IU, so this script can be run repeatedly while wiring up a client.

Standard library only (urllib + json). Python 3.8+.

Authentication — one of:
  * Service token:  KIRK_CF_CLIENT_ID + KIRK_CF_CLIENT_SECRET against the bare
                    /mcp path.
  * Connector URL:  KIRK_MCP_URL set to a personal connector URL, no headers.

    export KIRK_CF_CLIENT_ID=...
    export KIRK_CF_CLIENT_SECRET=...
    python3 kirk_quickstart.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("KIRK_MCP_URL", "https://kirk-mcp.kavara.ai/mcp")
CLIENT_ID = os.environ.get("KIRK_CF_CLIENT_ID")
CLIENT_SECRET = os.environ.get("KIRK_CF_CLIENT_SECRET")

# Cloudflare rejects Python's default User-Agent on this zone with a 1010
# "browser signature banned" error, which surfaces as a 403 that looks like an
# auth failure and is not one. Always send an explicit User-Agent.
USER_AGENT = "kirk-quickstart/1.0"

PROTOCOL_VERSION = "2025-06-18"


class KirkClient:
    def __init__(self, url, client_id=None, client_secret=None):
        self.url = url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        }
        if client_id and client_secret:
            self.headers["CF-Access-Client-Id"] = client_id
            self.headers["CF-Access-Client-Secret"] = client_secret
        self.session_id = None

    def _post(self, payload):
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(), method="POST"
        )
        for k, v in self.headers.items():
            req.add_header(k, v)
        if self.session_id:
            req.add_header("Mcp-Session-Id", self.session_id)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                return self._parse(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 403:
                raise SystemExit(
                    f"403 from the endpoint. Check KIRK_CF_CLIENT_ID / "
                    f"KIRK_CF_CLIENT_SECRET, and that a User-Agent is set.\n{body}"
                )
            raise SystemExit(f"HTTP {e.code}: {body}")

    @staticmethod
    def _parse(raw):
        """Responses arrive as SSE: one or more 'data: {json}' lines."""
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return json.loads(raw) if raw.strip() else {}

    def connect(self):
        self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "kirk-quickstart", "version": "1.0"},
            },
        })
        self._post({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

    def call(self, tool, arguments=None):
        resp = self._post({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": arguments or {}},
        })
        result = resp.get("result", {})
        if result.get("isError"):
            text = result.get("content", [{}])[0].get("text", "unknown error")
            raise SystemExit(f"{tool} failed: {text}")
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])


def main():
    if "/mcp/k_" not in URL and not (CLIENT_ID and CLIENT_SECRET):
        raise SystemExit(
            "Set KIRK_CF_CLIENT_ID and KIRK_CF_CLIENT_SECRET, or point "
            "KIRK_MCP_URL at a personal connector URL."
        )

    kirk = KirkClient(URL, CLIENT_ID, CLIENT_SECRET)
    kirk.connect()

    # 1. Engine identity. Record this sha alongside any result you keep --
    #    results from different engine builds are not interchangeable.
    engine = kirk.call("kirk_verify_engine")
    print(f"engine   {engine['engine_name']}  sha {engine['kirk_version'][:16]}...")

    # 2. Model catalogue.
    models = kirk.call("kirk_list_models")
    ids = models.get("models") or models.get("model_ids") or models
    print(f"models   {ids}")

    # 3. Render a book snapshot. The ENGINE builds the tensor -- you supply
    #    10 bid and 10 ask prices, level 1 first. Nothing is scored here.
    bid = [223.09 - 0.01 * i for i in range(10)]
    ask = [223.10 + 0.01 * i for i in range(10)]
    t = kirk.call("kirk_render_book", {"bid_px": bid, "ask_px": ask})
    print(
        f"tensor   shape={t['shape']} dtype={t['dtype']} "
        f"non_zero={t['non_zero_cells']} mid={t['mid_price']}"
    )

    cost = engine.get("_cost", {})
    print(f"cost     {cost.get('iu_session', 0)} IU this session (all three are free)")


if __name__ == "__main__":
    sys.exit(main())
