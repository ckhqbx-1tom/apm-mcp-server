from pathlib import Path

import pytest

from apm_mcp.config import Settings
from apm_mcp.errors import APMError


def test_missing_required_values():
    with pytest.raises(APMError, match="APM_API_URL"):
        Settings.from_env({})
    with pytest.raises(APMError, match="APM_API_KEY"):
        Settings.from_env({"APM_API_URL": "https://apm.example"})


def test_defaults_and_url_normalization():
    result = Settings.from_env({"APM_API_URL": "https://apm.example:8443///", "APM_API_KEY": "secret"})
    assert result.api_url == "https://apm.example:8443"
    assert result.verify_tls is True
    assert result.read_only is True
    assert result.connect_timeout == 10
    assert result.read_timeout == 30
    assert result.mcp_transport == "stdio"
    assert result.mcp_host == "127.0.0.1"
    assert result.mcp_port == 18082
    assert result.mcp_sse_path == "/sse"
    assert result.mcp_message_path == "/messages/"


def test_url_rejects_endpoint_path_and_credentials():
    with pytest.raises(APMError, match="endpoint path"):
        Settings.from_env({"APM_API_URL": "https://apm.example/AppManager/json", "APM_API_KEY": "secret"})
    with pytest.raises(APMError, match="credential-free"):
        Settings.from_env({"APM_API_URL": "https://user:pass@apm.example", "APM_API_KEY": "secret"})


def test_timeout_and_boolean_validation():
    base = {"APM_API_URL": "https://apm.example", "APM_API_KEY": "secret"}
    with pytest.raises(APMError, match="number"):
        Settings.from_env(base | {"APM_READ_TIMEOUT": "never"})
    with pytest.raises(APMError, match="true or false"):
        Settings.from_env(base | {"APM_VERIFY_TLS": "maybe"})


def test_custom_ca_must_be_readable(tmp_path: Path):
    with pytest.raises(APMError, match="readable"):
        Settings.from_env({"APM_API_URL": "https://apm.example", "APM_API_KEY": "x", "APM_CA_BUNDLE": str(tmp_path / "none")})


def test_sse_transport_configuration():
    result = Settings.from_env({
        "APM_API_URL": "https://apm.example", "APM_API_KEY": "secret",
        "APM_MCP_TRANSPORT": "sse", "APM_MCP_HOST": "0.0.0.0",
        "APM_MCP_PORT": "19090", "APM_MCP_SSE_PATH": "/events",
        "APM_MCP_MESSAGE_PATH": "/inbox/",
    })
    assert result.mcp_transport == "sse"
    assert result.mcp_host == "0.0.0.0"
    assert result.mcp_port == 19090
    assert result.mcp_sse_path == "/events"
    assert result.mcp_message_path == "/inbox/"


@pytest.mark.parametrize("transport", ["http", "streamable-http", "websocket"])
def test_invalid_transport(transport):
    with pytest.raises(APMError) as caught:
        Settings.from_env({
            "APM_API_URL": "https://apm.example", "APM_API_KEY": "secret",
            "APM_MCP_TRANSPORT": transport,
        })
    assert caught.value.code == "configuration_error"


@pytest.mark.parametrize("port", ["0", "65536", "abc"])
def test_invalid_mcp_port(port):
    with pytest.raises(APMError) as caught:
        Settings.from_env({
            "APM_API_URL": "https://apm.example", "APM_API_KEY": "secret",
            "APM_MCP_PORT": port,
        })
    assert caught.value.code == "configuration_error"


@pytest.mark.parametrize("name,value", [
    ("APM_MCP_SSE_PATH", "sse"),
    ("APM_MCP_MESSAGE_PATH", "messages/"),
])
def test_invalid_mcp_paths(name, value):
    with pytest.raises(APMError) as caught:
        Settings.from_env({
            "APM_API_URL": "https://apm.example", "APM_API_KEY": "secret", name: value,
        })
    assert caught.value.code == "configuration_error"


def test_empty_mcp_host():
    with pytest.raises(APMError) as caught:
        Settings.from_env({
            "APM_API_URL": "https://apm.example", "APM_API_KEY": "secret",
            "APM_MCP_HOST": "   ",
        })
    assert caught.value.code == "configuration_error"
