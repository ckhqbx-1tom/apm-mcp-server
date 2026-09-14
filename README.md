# Applications Manager MCP Server

这是一个面向 ManageEngine Applications Manager 的独立、只读 MCP Server。它通过 MCP `stdio` 协议向 AI Agent、ClawOps 或其他 MCP 客户端提供统一的告警、监视器和性能指标查询能力。

Applications Manager API Key 只由 MCP Server 从环境变量读取，不会出现在工具输入参数或正常工具输出中。

## 架构

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
ManageEngine Applications Manager
```

当前版本只提供查询工具，不包含告警确认、清除、修改配置或任意 REST 请求等写操作。

## MCP 工具

### `GetAlarms`

查询当前或历史告警，支持严重级别、资源、监视器名称、确认状态和时间范围等过滤条件，并限制单次返回数量。

### `GetAlarmDetails`

获取单条告警的完整上下文，并在能够可靠识别资源时补充监视器信息。不会生成 Applications Manager 未提供的 alarm ID。

### `GetAlarmNotes`

使用真实的 resource ID 与 attribute ID 读取现有告警 annotations；不会添加或修改备注。

### `SearchMonitors`

按名称、监视器类型、IP 地址、自定义字段或全部字段搜索监视器。

### `ListMonitors`

以有界分页结果浏览 monitor inventory，并支持官方 monitor type/resource ID 查询及状态、分组等防御性过滤。

### `GetMonitorSummary`

返回单个监视器的汇总信息，包括健康状态、可用性、主机信息、管理状态和当前指标。

### `GetServerContext`

根据监视器资源和 API 返回的真实主机信息解析 server 及相关 services，不从名称或 DNS 猜测 IP。

### `GetMonitorRelationships`

读取指定资源的 Health/Availability dependency mapping。部分 Applications Manager 版本要求管理员角色。

### `GetMonitorGroupTopology`

读取一个 Monitor Group 的成员和直接子组，结果有硬性数量限制。

### `ListMonitorMetrics`

列出一个 monitor 当前可查询的 metric metadata、真实 attribute ID 和当前值。

### `GetPerformanceMetrics`

返回监视器的当前或历史性能指标，保留 Applications Manager attribute ID、指标名称、单位、时间戳和数值。

## 环境变量

### 必填变量

| 变量 | 说明 | 示例 |
|---|---|---|
| `APM_API_URL` | Applications Manager 基础 URL，不要包含 `/AppManager/json`、`/AppManager/xml` 或 `/api/v3` | `https://apm.example.com:8443` |
| `APM_API_KEY` | Applications Manager API Key | `REDACTED` |

### 可选变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `APM_VERIFY_TLS` | `true` | 是否验证 Applications Manager TLS 证书 |
| `APM_CA_BUNDLE` | 未设置 | 自定义 CA 证书文件路径，文件必须存在且可读 |
| `APM_CONNECT_TIMEOUT` | `10` | 连接超时秒数 |
| `APM_READ_TIMEOUT` | `30` | 读取超时秒数 |
| `APM_MCP_READ_ONLY` | `true` | 只读模式；当前 11 个工具全部为查询操作 |
| `APM_LOG_LEVEL` | `INFO` | stderr 日志级别 |

TLS 验证默认开启，程序不会因证书错误自动降级为不安全连接。生产环境建议配置可信证书，或通过 `APM_CA_BUNDLE` 提供企业 CA。

如果测试环境使用自签名证书，可以显式设置：

```bash
APM_VERIFY_TLS=false
```

此时服务会向 stderr 输出安全警告。不要在生产环境中关闭 TLS 验证。

## Docker 部署

### 构建镜像

在项目根目录执行：

```bash
docker build -t apm-mcp-server:latest .
```

### 启动服务

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

注意事项：

- 必须保留 `-i`，MCP 客户端通过 stdin/stdout 与容器通信。
- stdout 专用于 MCP 协议消息，普通日志输出到 stderr。
- 容器默认使用非 root 用户 `apm`。
- API Key 不应直接写入 Dockerfile、代码、README 或版本控制文件。

测试环境使用自签名证书时，将上述参数改为：

```bash
-e APM_VERIFY_TLS="false"
```

## MCP 客户端配置

通用 Docker stdio 配置示例：

```json
{
  "mcpServers": {
    "applications-manager": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--cap-drop=ALL",
        "-e",
        "APM_API_URL",
        "-e",
        "APM_API_KEY",
        "-e",
        "APM_VERIFY_TLS",
        "-e",
        "APM_MCP_READ_ONLY",
        "apm-mcp-server:latest"
      ],
      "env": {
        "APM_API_URL": "https://apm.example.com:8443",
        "APM_API_KEY": "REDACTED",
        "APM_VERIFY_TLS": "true",
        "APM_MCP_READ_ONLY": "true"
      }
    }
  }
}
```

不同 MCP 客户端的配置文件位置和外层字段可能不同，但启动命令必须保留 Docker 的交互式 stdin。

## 本地开发

项目要求 Python 3.11 或更高版本。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

直接启动本地 stdio Server：

```bash
export APM_API_URL="https://apm.example.com:8443"
export APM_API_KEY="REDACTED"
apm-mcp-server
```

启动后终端不会显示普通交互界面，因为进程正在等待 MCP stdio 协议消息。

## 安全设计

- API Key 不属于任何 MCP 工具的输入 schema。
- v3 与旧版 API 的认证差异封装在共享 HTTP Client 中。
- HTTP 请求日志不会输出包含认证信息的完整 URL 或 Header。
- JSON 和 XML 响应统一转换为 JSON 兼容结构。
- XML 使用安全解析器，不允许外部实体展开。
- TLS 验证默认开启，自定义 CA 不可用时直接报错。
- 上游错误以结构化错误返回，不向 MCP 输出堆栈或 secret-bearing 请求对象。
- 告警和搜索结果有最大数量限制。
- 不提供原始 API、任意 URL 或写操作逃生通道。

## Applications Manager 版本兼容

不同 Applications Manager 版本的认证方式、字段名称和请求参数可能不同。当前实现将版本差异限制在 HTTP Client 和 normalization 层：

- `/api/v3/*` 使用内部 `Authorization` Header。
- `/AppManager/json/*` 与 `/AppManager/xml/*` 使用内部 API Key 参数。
- `RESOURCEID`、`ResourceId`、`resourceId` 等字段会归一化为 `resource_id`。
- 上游缺少的字段返回 `null` 或省略，不会猜测资源 ID、IP 地址或指标值。
- 不支持或无法安全解析的响应会返回明确错误。

## Applications Manager API 映射

| MCP 工具 | Applications Manager API |
|---|---|
| `GetAlarms` | `GET /api/v3/alarms`，使用 `view=Extended`、服务端过滤和分页 |
| `GetAlarmDetails` | `GET /api/v3/alarms`，必要时使用 `ListMonitor` 补充资源信息 |
| `GetAlarmNotes` | `POST /AppManager/json/AlarmAction`，固定 `action=ListAnnotations` |
| `SearchMonitors` | `GET /AppManager/json/Search` |
| `ListMonitors` | `GET /AppManager/json/ListMonitor` |
| `GetMonitorSummary` | `ListMonitor` + `ListServer` + `GetMonitorData` |
| `GetServerContext` | `ListMonitor` + `ListServer` |
| `GetMonitorRelationships` | `GET /AppManager/xml/listDependencies` |
| `GetMonitorGroupTopology` | `GET /AppManager/json/ListMGDetails` |
| `ListMonitorMetrics` | `GET /AppManager/xml/GetMonitorData` |
| `GetPerformanceMetrics` | 当前指标使用 `GetMonitorData`，历史指标使用 `ShowPolledData` |

## 0.1.0 Release Scope

0.1.0 固定提供以下 11 个只读 Tool：

- 告警：`GetAlarms`、`GetAlarmDetails`、`GetAlarmNotes`
- 监视器：`SearchMonitors`、`ListMonitors`、`GetMonitorSummary`、`GetServerContext`
- 关系与分组：`GetMonitorRelationships`、`GetMonitorGroupTopology`
- 指标：`ListMonitorMetrics`、`GetPerformanceMetrics`

本版本明确不包含 `PollMonitorNow`、`AddAlarmNote`、告警 acknowledge/pickup、unacknowledge/unpickup、`ClearAlarm`、monitor CRUD、阈值或配置修改、任意 raw REST 调用、SSH 或自动修复能力。

## 已验证范围

- Unit tests：本地发布前测试已通过。
- Official-response fixtures：兼容性测试已通过，覆盖 V3 alarm、Search、ListMonitor、ListServer、GetMonitorData、ShowPolledData RawData/ArchiveData 以及 legacy JSON/XML 业务错误。
- GitHub Actions CI：已配置 Python 3.11/3.12 测试、MCP stdio smoke test 和独立 Docker build；CI 不使用真实 APM 或 secret。
- Docker build：本地发布前构建已通过，镜像为 `apm-mcp-server:latest`。
- MCP protocol smoke test：通过真实 stdio transport 完成 `initialize`、`tools/list` 和正常退出；严格验证 11 个只读 Tool 及 schema 不含认证字段。
- Real Applications Manager integration：此前已完成测试实例的五个 P0 工具验证；P1 中已验证 inventory、server context、metric metadata、monitor-group topology、空 dependency 结果和 annotations 响应。本轮 release hardening 未将 mock/fixture 测试视为真实 E2E，是否重新验证以发布报告为准。

验证状态描述针对当前代码版本和已测试的 Applications Manager 实例。不同版本仍可能存在响应字段或可选参数差异；遇到无法可靠识别的响应时，服务会 fail closed。

## 错误格式

工具错误使用统一结构：

```json
{
  "error": {
    "code": "connection_error",
    "message": "Unable to connect to Applications Manager."
  }
}
```

常见错误代码包括：

- `configuration_error`
- `authentication_error`
- `authorization_error`
- `connection_error`
- `tls_error`
- `timeout`
- `not_found`
- `invalid_request`
- `upstream_error`
- `parse_error`
- `unsupported_response`
- `ambiguous_alarm`
- `ambiguous_resource`

## 当前范围

当前版本定位为只读监控适配器。以下功能不在当前版本范围内：

- 确认、取消确认或清除告警
- 添加或修改告警备注（读取备注已支持）
- 立即轮询监视器
- 创建、删除或修改监视器
- 修改阈值或 Applications Manager 配置
- 原始 REST API 调用
- 自动修复、SSH 或目标主机管理
