# xbbg-mcp

Stdio MCP server for Bloomberg request/response workflows backed by `xbbg-async`.

This binary is intended for coding agents such as Claude Code and OpenCode that can launch a local MCP server process and call tools over stdio.

## What it exposes

The current server exposes request/response tools only:

- `bdp` - reference data
- `bdh` - historical data
- `bds` - bulk data
- `bdib` - intraday bars
- `bql` - Bloomberg Query Language
- `bsrch` - Bloomberg search
- `bflds` - field metadata lookup
- `request` - generic raw/custom request path

Responses are returned as bounded structured JSON with Arrow schema metadata so an agent can inspect the shape without receiving an unbounded payload.

## Install from GitHub Releases

For macOS arm64 and Linux amd64, install the latest wrapper + binary pair with:

```bash
curl -fsSL https://raw.githubusercontent.com/alpha-xone/xbbg/main/scripts/install-xbbg-mcp.sh | sh
```

To install a specific release:

```bash
curl -fsSL https://raw.githubusercontent.com/alpha-xone/xbbg/main/scripts/install-xbbg-mcp.sh | sh -s -- 1.0.0
```

The installer places two files in `~/.local/bin/` by default:

- `xbbg-mcp` - launcher wrapper
- `xbbg-mcp-real` - compiled binary

GitHub release assets include only the launcher wrapper and compiled xbbg binary. They do **not** include Bloomberg SDK files or the Bloomberg runtime; you must provide those locally.

The wrapper locates the Bloomberg runtime in this order:

1. `XBBG_MCP_LIB_DIR`
2. `BLPAPI_LIB_DIR`
3. `BLPAPI_ROOT`
4. vendored SDK under `vendor/blpapi-sdk/`
5. the official Python `blpapi` package

If you install Bloomberg's Python package, the wrapper can usually run without any extra shell configuration:

```bash
pip install blpapi --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/
```

Windows release assets are attached as `.zip` files, but the convenience installer currently targets macOS/Linux only.

## Build from source

```bash
bash ./scripts/sdktool.sh
cargo build --release -p xbbg-mcp --locked
./scripts/xbbg-mcp
```

## Claude Code

```bash
claude mcp add --transport stdio xbbg -- ~/.local/bin/xbbg-mcp
```

## OpenCode

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "xbbg": {
      "type": "local",
      "command": ["/Users/you/.local/bin/xbbg-mcp"],
      "enabled": true
    }
  }
}
```

## Runtime environment

`xbbg-mcp` accepts the same engine-oriented connection settings as the Rust core, with MCP-prefixed names taking precedence where available.

Common settings:

- `XBBG_MCP_HOST` / `XBBG_HOST`
- `XBBG_MCP_PORT` / `XBBG_PORT`
- `XBBG_MCP_AUTH_METHOD` / `XBBG_AUTH_METHOD`
- `XBBG_MCP_APP_NAME`
- `XBBG_MCP_DIR_PROPERTY`
- `XBBG_MCP_USER_ID`
- `XBBG_MCP_IP_ADDRESS`
- `XBBG_MCP_TOKEN`
- `XBBG_MCP_REQUEST_POOL_SIZE`
- `XBBG_MCP_MAX_ROWS`
- `XBBG_MCP_MAX_STRING_CHARS`

Supported auth methods:

- `none`
- `user`
- `app`
- `userapp`
- `dir`
- `manual`
- `token`

## Smoke test

After building locally, verify the stdio handshake and a few live requests with:

```bash
uv run python -X utf8 scripts/xbbg_mcp_smoke.py
```

That script expects a live Bloomberg connection and a locally built `target/debug/xbbg-mcp` binary, or `target/release/xbbg-mcp` if no debug build is present.
