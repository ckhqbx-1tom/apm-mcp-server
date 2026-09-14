# Applications Manager MCP Server

A standalone, read-only MCP integration for ManageEngine Applications Manager. It runs over MCP stdio and keeps the Applications Manager API key inside the server process.

## Tools

- `GetAlarms`: bounded alarm listing and filtering
- `GetAlarmDetails`: alarm and resource context
- `SearchMonitors`: monitor lookup by name, type, IP, custom fields, or all fields
- `GetMonitorSummary`: consolidated monitor, server, and current metric context
- `GetPerformanceMetrics`: current or historical metrics with preserved attribute IDs

## Configuration

Required: `APM_API_URL` (base URL only) and `APM_API_KEY`.

Optional variables and defaults:

| Variable | Default | Purpose |
|---|---:|---|
| `APM_VERIFY_TLS` | `true` | Verify the upstream TLS certificate |
| `APM_CA_BUNDLE` | unset | Readable custom CA bundle path |
| `APM_CONNECT_TIMEOUT` | `10` | Connect timeout in seconds |
| `APM_READ_TIMEOUT` | `30` | Read timeout in seconds |
| `APM_MCP_READ_ONLY` | `true` | Read-only policy (all P0 tools are queries) |
| `APM_LOG_LEVEL` | `INFO` | stderr log level |

`APM_API_URL` should look like `https://apm.example.com:8443`; endpoint paths are added internally. TLS is never disabled automatically.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

## Docker

```bash
docker build -t apm-mcp-server:latest .
docker run \
  -e APM_API_URL="https://apm.example.com:8443" \
  -e APM_API_KEY="REDACTED" \
  -e APM_VERIFY_TLS="true" \
  -e APM_MCP_READ_ONLY="true" \
  --cap-drop=ALL -i --rm apm-mcp-server:latest
```

Generic MCP client configuration:

```json
{
  "mcpServers": {
    "applications-manager": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "--cap-drop=ALL", "-e", "APM_API_URL", "-e", "APM_API_KEY", "apm-mcp-server:latest"],
      "env": {
        "APM_API_URL": "https://apm.example.com:8443",
        "APM_API_KEY": "REDACTED"
      }
    }
  }
}
```

Logs go to stderr; stdout is reserved for MCP protocol messages. The server has no raw-request escape hatch and exposes no mutation tools.
