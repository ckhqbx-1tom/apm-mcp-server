# AGENTS.md

## Project Goal

Build a standalone MCP Server for ManageEngine Applications Manager.

The MCP Server will act as a controlled integration layer between AI Agents / ClawOps and ManageEngine Applications Manager REST APIs.

The first implementation should closely follow the deployment model of the existing ManageEngine OpManager MCP integration:

```text
AI Agent / ClawOps
        │
        │ MCP stdio
        ▼
Docker Container
apm-mcp-server
        │
        │ HTTPS REST API
        ▼
ManageEngine
Applications Manager
```

The MCP Server must run as a Docker container and communicate with MCP clients using `stdio`.

Applications Manager connection information and credentials must be supplied using environment variables.

The AI Agent must never receive or provide the Applications Manager API key.

---

# 1. Primary Design Principles

The implementation must follow these principles.

## 1.1 MCP is an abstraction layer

Do not expose raw Applications Manager REST API structure directly to the AI Agent.

The MCP tools should expose stable operational concepts such as:

```text
alarm
monitor
resource
metric
relationship
action
```

Do not design MCP tools around individual vendor endpoint names unless there is a strong reason.

For example:

Good:

```text
GetAlarms
GetAlarmDetails
SearchMonitors
GetMonitorSummary
GetPerformanceMetrics
```

Avoid exposing tools such as:

```text
CallListMonitorAPI
CallShowPolledData
RawAPMRequest
ExecuteAPMAPI
```

The Applications Manager REST API is an implementation detail behind the MCP layer.

---

## 1.2 Credentials must not enter model context

Applications Manager authentication is configured through environment variables.

Required variables:

```text
APM_API_URL
APM_API_KEY
```

The API key:

* must never be part of an MCP tool input schema;
* must never be returned by an MCP tool;
* must never be printed to stdout;
* must never appear in normal logs;
* must never be included in exception messages;
* must never be returned in diagnostic output.

All REST API authentication must be handled internally by the MCP server.

---

## 1.3 Default to read-only

The first release is read-only by default.

Environment variable:

```text
APM_MCP_READ_ONLY=true
```

Default behavior:

```text
APM_MCP_READ_ONLY=true
```

When read-only mode is enabled, only query tools should be registered or executable.

Action tools such as:

```text
AcknowledgeAlarm
UnacknowledgeAlarm
ClearAlarm
AddAlarmNote
PollMonitorNow
```

must not be exposed in the first P0 implementation unless explicitly added later.

Do not silently downgrade or bypass read-only mode.

---

## 1.4 Fail closed

If configuration, authentication, TLS, parsing, upstream connectivity, or API behavior cannot be safely determined, return an explicit error.

Do not:

* guess resource IDs;
* guess monitor IP addresses;
* fabricate metrics;
* reuse stale results as current data;
* silently fall back to unrelated API endpoints;
* disable TLS verification automatically;
* expose raw authentication information;
* retry destructive/action APIs using alternative methods.

---

# 2. First Release Scope

The first implementation must focus only on the following five P0 MCP tools:

```text
GetAlarms
GetAlarmDetails
SearchMonitors
GetMonitorSummary
GetPerformanceMetrics
```

Do not implement a large number of additional tools before these five are complete, tested, and documented.

The goal of the first release is to support the following workflow:

```text
Applications Manager alarm
        ↓
GetAlarms
        ↓
GetAlarmDetails
        ↓
identify monitor/resource
        ↓
SearchMonitors / GetMonitorSummary
        ↓
GetPerformanceMetrics
        ↓
AI / ClawOps analysis
```

---

# 3. Applications Manager API Mapping

The MCP layer may combine multiple Applications Manager APIs internally.

Use the following APIs as the primary implementation sources.

## 3.1 Alarms

Preferred endpoint:

```text
GET /api/v3/alarms
```

Use this API for:

```text
GetAlarms
GetAlarmDetails
```

Relevant fields may include:

```text
resourceId
displayName
monitorType
parentResourceId
severity
alertCreationTime
alertModifiedTime
message
technician
attributeId
attributeName
latestNote
acknowledged
startTime
endTime
duration
```

Do not assume every Applications Manager version returns every field.

Implement defensive parsing.

Unknown or missing fields should be returned as `null` or omitted according to the response model, rather than causing fabricated values.

---

## 3.2 Monitor Search

Preferred endpoint:

```text
/AppManager/json/Search
```

Use this for:

```text
SearchMonitors
```

Typical searchable attributes include:

```text
displayname
monitortype
ipaddress
customfields
all
```

Normalize returned monitor data into the MCP monitor model.

---

## 3.3 Monitor Inventory

Preferred endpoint:

```text
/AppManager/json/ListMonitor
```

Use this as one source for:

```text
GetMonitorSummary
```

It may provide:

```text
resource ID
display name
monitor type
health
availability
managed state
monitor groups
```

---

## 3.4 Server Context

Applications Manager server information may be retrieved using:

```text
/AppManager/json/ListServer
```

Use this internally when necessary for `GetMonitorSummary`.

Important output fields include:

```text
server name
IP address
resource ID
server type
associated monitors/services
```

This is especially important for future ClawOps integration because ClawOps may need the actual host IP associated with an application monitor.

Do not infer an IP address from a monitor name when the API does not return one.

---

## 3.5 Current Monitor Data

Preferred endpoint:

```text
/AppManager/xml/GetMonitorData
```

Use this for current/latest metric information.

This API may return data such as:

```text
health
availability
last poll time
CPU
memory
disk
response time
child monitor data
```

Applications Manager may return XML.

XML parsing must be isolated inside the API/client layer.

MCP tools must return normalized JSON-compatible Python structures.

Do not expose raw XML unless explicitly needed for debugging and never by default.

---

## 3.6 Historical Performance Data

Preferred endpoint:

```text
/AppManager/json/ShowPolledData
```

Expected parameters may include:

```text
resourceid
attributeID
period
startDate
endDate
```

This API should be used by:

```text
GetPerformanceMetrics
```

when historical data is requested.

Preserve the Applications Manager attribute ID.

It is required to correlate metric definitions and historical metric data.

---

# 4. MCP Tool Contracts

Tool names should remain stable even if the underlying Applications Manager API changes.

Use clear descriptions so an AI Agent knows when to call each tool.

---

## 4.1 GetAlarms

Purpose:

Return current or historical Applications Manager alarms.

Suggested input:

```json
{
  "severity": null,
  "resource_id": null,
  "monitor_name": null,
  "monitor_group": null,
  "acknowledged": null,
  "start_time": null,
  "end_time": null,
  "page": 1,
  "page_size": 100
}
```

All filters should be optional unless the upstream API requires otherwise.

Suggested normalized output:

```json
{
  "alarms": [
    {
      "alarm_id": "...",
      "resource_id": "...",
      "resource_name": "...",
      "monitor_type": "...",
      "parent_resource_id": "...",
      "severity": "...",
      "message": "...",
      "attribute_id": "...",
      "attribute_name": "...",
      "acknowledged": false,
      "created_at": "...",
      "modified_at": "...",
      "latest_note": "..."
    }
  ],
  "page": 1,
  "page_size": 100,
  "has_more": false
}
```

Do not invent `alarm_id` if Applications Manager does not expose an independent alarm ID.

If the Applications Manager alarm identity is based on another stable combination, preserve that explicitly and document it.

---

## 4.2 GetAlarmDetails

Purpose:

Return the full context required to analyze a specific Applications Manager alarm.

Input should identify the alarm using the most reliable identifier supported by Applications Manager.

Possible input:

```json
{
  "alarm_id": "...",
  "resource_id": "...",
  "attribute_id": "..."
}
```

Do not require all identifiers if one is sufficient.

Normalized response should include:

```json
{
  "alarm": {
    "alarm_id": "...",
    "resource_id": "...",
    "resource_name": "...",
    "monitor_type": "...",
    "parent_resource_id": "...",
    "severity": "...",
    "message": "...",
    "attribute_id": "...",
    "attribute_name": "...",
    "acknowledged": false,
    "created_at": "...",
    "modified_at": "...",
    "latest_note": "..."
  },
  "resource": {
    "resource_id": "...",
    "display_name": "...",
    "monitor_type": "...",
    "host": null
  }
}
```

If server/host context can be safely determined, include it.

If it cannot be determined, return:

```json
"host": null
```

Do not guess.

---

## 4.3 SearchMonitors

Purpose:

Resolve natural monitor names, IP addresses, application names, and other search terms into Applications Manager resources.

Suggested input:

```json
{
  "query": "payment-api",
  "search_by": "all",
  "limit": 50
}
```

Allowed `search_by` values should be limited to known supported values, for example:

```text
all
displayname
monitortype
ipaddress
customfields
```

Suggested output:

```json
{
  "monitors": [
    {
      "resource_id": "...",
      "display_name": "...",
      "monitor_type": "...",
      "health": "...",
      "availability": "...",
      "health_message": "...",
      "availability_message": "...",
      "ip_address": null
    }
  ]
}
```

---

## 4.4 GetMonitorSummary

Purpose:

Provide a consolidated overview of one Applications Manager resource.

This MCP tool may internally combine:

```text
ListMonitor
ListServer
GetMonitorData
```

Input:

```json
{
  "resource_id": "..."
}
```

Suggested output:

```json
{
  "resource_id": "...",
  "display_name": "...",
  "monitor_type": "...",
  "health": "...",
  "availability": "...",
  "managed": true,
  "last_polled_at": "...",
  "host": {
    "hostname": null,
    "ip_address": null,
    "server_type": null,
    "resource_id": null
  },
  "monitor_groups": [],
  "related_services": [],
  "current_metrics": []
}
```

This tool is intended to provide enough context for an AI Agent to understand:

```text
What is this monitor?
What host does it belong to?
What is its current health?
What application/server context exists?
What are the latest important metrics?
```

Avoid returning huge raw payloads.

Normalize and limit output to operationally useful information.

---

## 4.5 GetPerformanceMetrics

Purpose:

Return current or historical metric data for one Applications Manager resource.

Suggested input:

```json
{
  "resource_id": "...",
  "attribute_id": null,
  "start_time": null,
  "end_time": null,
  "period": null
}
```

Behavior:

If no historical range is provided, current/latest monitor data may be returned using `GetMonitorData`.

If historical range or period is provided, use `ShowPolledData`.

Suggested output:

```json
{
  "resource_id": "...",
  "metrics": [
    {
      "attribute_id": "...",
      "name": "...",
      "unit": "...",
      "current_value": null,
      "samples": [
        {
          "timestamp": "...",
          "value": 92.1
        }
      ],
      "summary": {
        "min": null,
        "max": null,
        "avg": null
      }
    }
  ]
}
```

Do not collapse all Applications Manager metrics into arbitrary generated names.

Preserve:

```text
attribute_id
metric name
unit
timestamp
value
```

when available.

---

# 5. Future P1 Tools

Do not implement these until the five P0 tools are stable.

Future tools may include:

```text
GetMonitorRelationships
AcknowledgeAlarm
UnacknowledgeAlarm
AddAlarmNote
GetAlarmNotes
ClearAlarm
PollMonitorNow
```

Potential underlying APIs:

```text
ListMonitorGroups
ListMGDetails
listDependencies
AlarmAction
PollNow
```

Action tools must remain disabled when:

```text
APM_MCP_READ_ONLY=true
```

Do not implement `UpdateAlarmNotes` unless Applications Manager provides a reliable supported API for modifying an existing note.

Do not emulate unsupported behavior.

---

# 6. Configuration

The MCP Server must be configured using environment variables.

Required:

```text
APM_API_URL
APM_API_KEY
```

Optional:

```text
APM_VERIFY_TLS=true
APM_CA_BUNDLE=
APM_CONNECT_TIMEOUT=10
APM_READ_TIMEOUT=30
APM_MCP_READ_ONLY=true
APM_LOG_LEVEL=INFO
```

`APM_API_URL` should contain only the Applications Manager base URL.

Example:

```text
https://apm.example.com:8443
```

Do not require users to include:

```text
/AppManager/json
/AppManager/xml
/api/v3
```

These paths belong inside the MCP implementation.

Normalize trailing slashes safely.

---

# 7. TLS Requirements

Default:

```text
APM_VERIFY_TLS=true
```

TLS verification must not be disabled automatically.

If:

```text
APM_VERIFY_TLS=false
```

is explicitly configured, log a warning without logging credentials.

Support custom CA bundles:

```text
APM_CA_BUNDLE=/certs/company-ca.pem
```

When a CA bundle is provided, validate that the path exists and is readable.

Do not silently fall back to insecure TLS.

---

# 8. Docker Requirements

Provide a Dockerfile.

The resulting container should be runnable approximately as follows:

```bash
docker run \
  -e APM_API_URL="https://apm.example.com:8443" \
  -e APM_API_KEY="REDACTED" \
  -e APM_VERIFY_TLS="true" \
  -e APM_MCP_READ_ONLY="true" \
  --cap-drop=ALL \
  -i \
  --rm \
  apm-mcp-server:latest
```

The MCP transport for the first release is:

```text
stdio
```

Do not add an HTTP MCP transport unless separately requested.

The process must write MCP protocol output to stdout.

Normal logs should go to stderr.

Never print startup banners or debugging text to stdout because this can corrupt MCP stdio communication.

---

# 9. Suggested Project Structure

Use a structure similar to:

```text
apm-mcp-server/
├── AGENTS.md
├── README.md
├── Dockerfile
├── .dockerignore
├── .gitignore
├── pyproject.toml
├── src/
│   └── apm_mcp/
│       ├── __init__.py
│       ├── server.py
│       ├── config.py
│       ├── client.py
│       ├── errors.py
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── alarms.py
│       │   ├── monitors.py
│       │   └── metrics.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── alarm.py
│       │   ├── monitor.py
│       │   └── metric.py
│       │
│       └── normalization/
│           ├── __init__.py
│           └── apm.py
│
└── tests/
    ├── test_config.py
    ├── test_client.py
    ├── test_alarms.py
    ├── test_monitors.py
    └── test_metrics.py
```

Keep MCP tool definitions separate from raw REST API access.

Architecture:

```text
MCP Tool
   ↓
Normalization / Service logic
   ↓
APM REST Client
   ↓
Applications Manager
```

Do not call `requests.get()` or `httpx.get()` directly from individual tool handlers.

All HTTP behavior must go through the shared APM client.

---

# 10. HTTP Client Requirements

Use a reusable HTTP client.

Preferred library:

```text
httpx
```

The client should handle:

```text
base URL
API key
TLS verification
custom CA bundle
connection timeout
read timeout
response decoding
JSON parsing
XML parsing
HTTP errors
Applications Manager errors
```

The API key injection mechanism should be isolated in this layer.

Do not spread authentication logic across tool implementations.

---

# 11. Error Model

Return structured, human-readable errors.

Suggested categories:

```text
configuration_error
authentication_error
authorization_error
connection_error
tls_error
timeout
not_found
invalid_request
upstream_error
parse_error
unsupported_response
```

Example:

```json
{
  "error": {
    "code": "connection_error",
    "message": "Unable to connect to Applications Manager."
  }
}
```

Do not expose:

```text
API keys
authorization headers
session tokens
raw secret-bearing request objects
stack traces containing credentials
```

Internal debugging information may be logged to stderr at DEBUG level, but must still redact secrets.

---

# 12. Secret Redaction

Implement secret redaction centrally.

At minimum redact:

```text
APM_API_KEY
Authorization
apikey
api_key
token
password
cookie
session
```

Never depend solely on developers remembering not to log credentials.

HTTP request logging must not dump sensitive headers or query parameters.

---

# 13. Pagination and Output Limits

Applications Manager may return large result sets.

MCP tools must support bounded output.

For alarms and search results:

* provide sensible default page sizes;
* enforce a maximum page size;
* return pagination metadata when possible.

Do not send thousands of alarm objects into model context by default.

Suggested default:

```text
page_size = 100
```

Suggested hard maximum:

```text
page_size = 500
```

This may be adjusted after real API testing.

---

# 14. Time Handling

Normalize timestamps when possible.

Prefer ISO 8601 output:

```text
2026-09-14T14:00:00+08:00
```

If Applications Manager returns epoch timestamps, convert them.

If the meaning or timezone of an upstream timestamp is uncertain, preserve the original timestamp separately rather than guessing.

Example:

```json
{
  "created_at": "...",
  "created_at_raw": "..."
}
```

---

# 15. Data Normalization

Applications Manager APIs may use inconsistent formats across endpoints and versions.

Normalize vendor-specific fields inside:

```text
normalization/
```

Examples:

```text
RESOURCEID
resourceId
resourceid
```

should become:

```text
resource_id
```

Similarly:

```text
DISPLAYNAME
displayName
```

should become:

```text
display_name
```

Do not let API-specific capitalization leak throughout the project.

---

# 16. XML Handling

Some Applications Manager APIs return XML.

Use a safe XML parser.

Do not enable external entity expansion.

Do not process external DTDs or network-loaded XML entities.

Convert required XML fields into normalized Python dictionaries before returning data to MCP tools.

---

# 17. Testing Requirements

The first implementation must include automated tests.

At minimum test:

## Configuration

* missing `APM_API_URL`;
* missing `APM_API_KEY`;
* URL normalization;
* TLS defaults;
* timeout parsing;
* read-only default.

## Authentication safety

Verify that the API key does not appear in:

* tool outputs;
* exceptions;
* normal logs.

## GetAlarms

Test:

* normal result;
* empty result;
* severity filter;
* pagination;
* malformed upstream response;
* authentication failure.

## GetAlarmDetails

Test:

* exact match;
* missing alarm;
* missing optional fields;
* monitor/resource enrichment.

## SearchMonitors

Test:

* name search;
* IP search;
* no matches;
* multiple matches;
* malformed API response.

## GetMonitorSummary

Test:

* monitor only;
* monitor + server context;
* monitor without IP;
* upstream partial failure.

Do not fabricate server context if enrichment fails.

## GetPerformanceMetrics

Test:

* current metrics;
* historical metrics;
* attribute ID handling;
* empty data;
* malformed numeric values;
* timestamp normalization.

---

# 18. Mocking Strategy

Do not require a real Applications Manager instance for the unit test suite.

Mock HTTP responses.

Create representative fixtures for:

```text
/api/v3/alarms
/AppManager/json/Search
/AppManager/json/ListMonitor
/AppManager/json/ListServer
/AppManager/xml/GetMonitorData
/AppManager/json/ShowPolledData
```

Real Applications Manager integration tests may be added separately.

Never commit real:

```text
APM_API_KEY
hostnames
customer addresses
production IP addresses
cookies
tokens
```

---

# 19. README Requirements

Create a README containing:

## What this project does

Explain that it provides an MCP interface for ManageEngine Applications Manager.

## Current tool list

Document the five P0 tools.

## Required environment variables

```text
APM_API_URL
APM_API_KEY
```

## Optional variables

Document TLS, timeout, logging, and read-only variables.

## Docker build

Example:

```bash
docker build -t apm-mcp-server:latest .
```

## Docker run

Example:

```bash
docker run \
  -e APM_API_URL="https://apm.example.com:8443" \
  -e APM_API_KEY="REDACTED" \
  -e APM_VERIFY_TLS="true" \
  -e APM_MCP_READ_ONLY="true" \
  --cap-drop=ALL \
  -i \
  --rm \
  apm-mcp-server:latest
```

## MCP client configuration

Provide a generic stdio Docker example.

Never place a real API key in documentation.

---

# 20. ClawOps Compatibility

The MCP Server should be designed so it can later act as a monitoring source for ClawOps.

ClawOps ultimately needs a normalized alarm context roughly equivalent to:

```json
{
  "source": "apm",
  "alarm_id": "...",
  "resource_id": "...",
  "resource_name": "...",
  "resource_type": "...",
  "host": "...",
  "severity": "...",
  "message": "...",
  "attribute": {
    "id": "...",
    "name": "..."
  },
  "triggered_at": "...",
  "metrics": []
}
```

Do not tightly couple the MCP server to the ClawOps repository.

The MCP server should remain independently usable by any MCP-compatible Agent.

However, normalize outputs in a way that makes future ClawOps integration straightforward.

---

# 21. Out of Scope for P0

Do not implement the following unless separately approved:

```text
alarm acknowledgement
alarm clearing
alarm notes
PollNow
monitor creation
monitor deletion
threshold modification
configuration modification
raw arbitrary REST execution
APM administration
credential modification
automatic remediation
SSH
ClawOps runtime execution
Windows target management
network device management
```

The first release is a monitoring/read-only MCP adapter.

---

# 22. Do Not Add a Raw API Escape Hatch

Do not implement tools such as:

```text
CallAPMApi
RawRequest
ExecuteREST
FetchURL
```

These would bypass the MCP semantic and security boundary.

Every exposed MCP tool must have a specific operational purpose and a bounded schema.

---

# 23. Version Compatibility

Applications Manager installations may differ by version.

Isolate version-specific behavior inside the APM client or adapter layer.

If an endpoint is unavailable:

* return a clear unsupported/upstream error;
* do not silently replace it with unrelated data;
* do not fabricate missing information.

A future capability-discovery mechanism may be added, but is not required for P0.

---

# 24. Implementation Order

Implement in this order:

```text
1. project skeleton
2. environment configuration
3. secure HTTP client
4. error model and secret redaction
5. MCP stdio server
6. GetAlarms
7. GetAlarmDetails
8. SearchMonitors
9. GetMonitorSummary
10. GetPerformanceMetrics
11. unit tests
12. Docker image
13. README
14. end-to-end smoke test
```

Do not start P1 action tools before the P0 implementation works end to end.

---

# 25. Completion Criteria

The P0 implementation is complete only when all of the following are true:

```text
Docker image builds successfully.
Container runs through stdio MCP transport.
APM_API_URL is configurable.
APM_API_KEY is configurable.
API key never appears in MCP output.
TLS verification defaults to enabled.
Read-only mode defaults to enabled.
Five P0 tools are available.
APM JSON responses are normalized.
APM XML responses are normalized.
Large responses are bounded.
Errors are structured.
Tests pass.
README contains usable deployment instructions.
```

The final result should allow an MCP client to run:

```bash
docker run \
  -e APM_API_URL="https://apm.example.com:8443" \
  -e APM_API_KEY="..." \
  -i \
  --rm \
  apm-mcp-server:latest
```

and then use MCP tools to inspect Applications Manager alarms, monitors, and performance data without exposing the Applications Manager API key to the AI Agent.

