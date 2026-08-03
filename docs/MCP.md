# MCP Integration — Step by Step

InferCache ships an MCP (Model Context Protocol) server. Any MCP client —
Cursor, Claude Desktop, Claude Code, Windsurf — can check the local cache
before spending tokens and store answers afterwards.

**Status:** **tested with Cursor.** Claude Desktop, Claude Code, and other MCP
clients are **testing in progress** (same server; client setup not fully validated yet).

Everything runs on your machine: stdio transport, SQLite at
`~/.infercache/cache.db`, zero network access.

## Tools exposed

| Tool | What it does |
|------|--------------|
| `cache_lookup` | Check cache before an LLM call (exact + semantic match) |
| `cache_store` | Save a prompt/response pair after an LLM call |
| `cache_stats` | Hit rate, tokens saved, estimated cost reduction |
| `cache_feedback` | Report a wrong cached answer (tunes thresholds) |
| `cache_clear` | Wipe the local cache |

## Step 1 — Install

```bash
pip install infercache
# verify:
infercache --version
```

## Step 2 — Test the server manually (optional)

```bash
infercache mcp
```

Then paste this line and press Enter — you should get a JSON response back:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize"}
```

Ctrl+C to exit. If that works, the server is healthy.

## Step 3 — Register with your client

### Cursor

Create (or edit) `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json`
for all projects:

```json
{
  "mcpServers": {
    "infercache": {
      "command": "infercache",
      "args": ["mcp"]
    }
  }
}
```

Reload Cursor. In **Settings → MCP** you should see `infercache` with 5 tools.

### Claude Desktop

Edit the config file:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "infercache": {
      "command": "infercache",
      "args": ["mcp"]
    }
  }
}
```

Restart Claude Desktop.

### Claude Code

```bash
claude mcp add infercache -- infercache mcp
```

### If `infercache` is not on PATH

Point at the Python executable instead:

```json
{
  "mcpServers": {
    "infercache": {
      "command": "python",
      "args": ["-m", "infercache.mcp"]
    }
  }
}
```

(On Windows with a venv: use the full path, e.g.
`C:\\path\\to\\.venv\\Scripts\\python.exe`.)

## Step 4 — Tell the agent to use it

MCP clients decide when to call tools. Add a rule so the agent uses the cache
consistently — e.g. in Cursor, create `.cursor/rules/infercache.mdc`:

```
Before answering questions that may repeat across sessions, call the
infercache cache_lookup tool. If it returns cache_hit=true, use that response.
After generating a new substantive answer, call cache_store to save it.
```

## Step 5 — Verify it works

Ask your agent something, then ask a paraphrase of the same question.
Check savings:

```bash
infercache stats
```

You should see `semantic_hits` > 0 and a growing `tokens_saved`.

## Options

```bash
infercache mcp --backend sqlite --sqlite-path D:\my\cache.db --similarity-threshold 0.65
```

| Flag | Default | Notes |
|------|---------|-------|
| `--backend` | `sqlite` | `memory` = non-persistent, `redis` = opt-in only |
| `--sqlite-path` | `~/.infercache/cache.db` | Shared across all MCP clients |
| `--similarity-threshold` | `0.55` | Raise for stricter semantic matching |

Because all clients default to the same SQLite file, an answer cached from
Claude Desktop is also a cache hit in Cursor.

## MCP vs Gateway — which to use?

| | MCP server | Gateway proxy |
|--|-----------|---------------|
| How it plugs in | Agent calls cache tools explicitly | Transparent — client just changes base URL |
| Caching is | Best-effort (agent decides) | Guaranteed on every request |
| Best for | Cursor/Claude Desktop chat workflows | SDKs, scripts, apps, Claude Code via `ANTHROPIC_BASE_URL` |

Run both if you like — they share the same local cache file.
