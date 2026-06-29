# Outlay MCP server

Query attributed AI spend from any MCP client — Claude Desktop / Claude Code, Cursor, or anything that
speaks the [Model Context Protocol](https://modelcontextprotocol.io). Once connected, the model can
**answer questions about your AI spend in natural language** ("what did the growth team spend?",
"what's our forecast and how accurate is it?", "should we commit?") because it has Outlay's tools.

This is the "metrics where the work happens" pattern — Outlay's numbers in the editor, not just a web
dashboard. Pure stdlib, read-only.

## Run it

```bash
# Demo data (bundled fixtures) — works out of the box:
python -m outlay.mcp_server

# Your data — point at a serialized report (outlay.serialize.to_dict / `outlay --json`):
OUTLAY_REPORT=/path/to/report.json python -m outlay.mcp_server
```

It speaks newline-delimited JSON-RPC 2.0 over stdio (the MCP stdio transport).

## Connect it to a client

**Claude Desktop / Claude Code** — add to your MCP config (`claude_desktop_config.json` or
`.mcp.json`):

```json
{
  "mcpServers": {
    "outlay": {
      "command": "python",
      "args": ["-m", "outlay.mcp_server"],
      "env": { "OUTLAY_REPORT": "/path/to/report.json" }
    }
  }
}
```

**Cursor** — add the same block under `mcpServers` in `.cursor/mcp.json`.

## Tools exposed

| Tool | What it answers |
|---|---|
| `spend_overview` | Total attributed spend, ticket coverage, spend-by-fidelity |
| `cost_drilldown` | Spend grouped by `team` / `class` / `status` / `ticket` |
| `cost_per_unit` | The hero metric — cost per delivered unit of work, overall + per class |
| `forecast` | Backlog forecast **with its leave-one-out back-test accuracy** |
| `recommendations` | Cheaper-model routing recommendations (net of rework) |
| `commitment_recommendation` | On-demand vs committed-spend, sized from the run-rate |

All read-only and metadata-only — consistent with the rest of Outlay. Nothing here mutates data,
routes a request, or sees a prompt/key.
