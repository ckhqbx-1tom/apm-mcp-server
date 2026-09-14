import ssl

import httpx
import pytest

from apm_mcp.client import APMClient, _is_tls_error
from apm_mcp.config import Settings
from apm_mcp.errors import APMError, redact


def settings(key="top-secret"):
    return Settings(api_url="https://apm.example", api_key=key)


@pytest.mark.asyncio
async def test_auth_is_injected_but_not_returned():
    async def handler(request):
        assert request.headers["Authorization"] == "top-secret"
        assert "apikey" not in request.url.params
        return httpx.Response(200, json={"data": []})
    async with APMClient(settings(), httpx.MockTransport(handler)) as client:
        assert await client.get_json("/api/v3/alarms") == {"data": []}


@pytest.mark.asyncio
async def test_legacy_auth_is_query_parameter():
    async def handler(request):
        assert request.url.params["apikey"] == "top-secret"
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"response": {"result": []}})
    async with APMClient(settings(), httpx.MockTransport(handler)) as client:
        await client.get_json("/AppManager/json/Search", {"query": "app"})


@pytest.mark.asyncio
async def test_auth_failure_does_not_expose_secret():
    async def handler(request):
        return httpx.Response(401, text="top-secret")
    async with APMClient(settings(), httpx.MockTransport(handler)) as client:
        with pytest.raises(APMError) as caught:
            await client.get_json("/x")
    assert caught.value.code == "authentication_error"
    assert "top-secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_invalid_json_and_safe_xml():
    async def handler(request):
        if request.url.path == "/json":
            return httpx.Response(200, text="not-json")
        return httpx.Response(200, text="<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><x>&e;</x>")
    async with APMClient(settings(), httpx.MockTransport(handler)) as client:
        with pytest.raises(APMError, match="invalid JSON"):
            await client.get_json("/json")
        with pytest.raises(APMError, match="invalid XML"):
            await client.get_xml("/xml")


@pytest.mark.asyncio
async def test_xml_is_converted_without_vendor_markup_leaking():
    async def handler(request):
        return httpx.Response(200, text='<response><metrics><metric attributeID="7" value="42" /></metrics></response>')
    async with APMClient(settings(), httpx.MockTransport(handler)) as client:
        assert await client.get_xml("/xml") == {
            "response": {"metrics": {"metric": {"attributeID": "7", "value": "42"}}}
        }


@pytest.mark.asyncio
async def test_empty_successful_xml_is_empty_data():
    async def handler(request):
        return httpx.Response(200, content=b"")
    async with APMClient(settings(), httpx.MockTransport(handler)) as client:
        assert await client.get_xml("/xml") == {}


def test_recursive_redaction():
    result = redact({"Authorization": "abc", "nested": {"api_key": "abc"}, "text": "value abc"}, ("abc",))
    assert "abc" not in str(result)


def test_nested_tls_error_detection():
    try:
        try:
            raise ssl.SSLCertVerificationError("certificate verify failed")
        except ssl.SSLError as inner:
            raise httpx.ConnectError("wrapped") from inner
    except httpx.ConnectError as outer:
        assert _is_tls_error(outer)
