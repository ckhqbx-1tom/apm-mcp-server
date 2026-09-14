from __future__ import annotations

import ssl
from typing import Any

import httpx
from defusedxml import ElementTree

from .config import Settings
from .errors import APMError


class APMClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        verify: bool | ssl.SSLContext = settings.verify_tls
        if settings.ca_bundle:
            verify = ssl.create_default_context(cafile=settings.ca_bundle)
        timeout = httpx.Timeout(settings.read_timeout, connect=settings.connect_timeout)
        self._http = httpx.AsyncClient(
            base_url=settings.api_url + "/", verify=verify, timeout=timeout,
            transport=transport, follow_redirects=False,
        )

    async def __aenter__(self) -> "APMClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._get(path, params)
        try:
            return response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise APMError("parse_error", "Applications Manager returned invalid JSON.") from exc

    async def get_xml(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._get(path, params)
        if not response.content.strip():
            return {}
        try:
            root = ElementTree.fromstring(response.content)
        except Exception as exc:
            raise APMError("parse_error", "Applications Manager returned invalid XML.") from exc
        return {root.tag: _xml_node(root)}

    async def _get(self, path: str, params: dict[str, Any] | None) -> httpx.Response:
        safe_params = {key: value for key, value in (params or {}).items() if value is not None}
        normalized_path = path.lstrip("/")
        headers: dict[str, str] = {}
        if normalized_path.startswith("api/v3/"):
            headers["Authorization"] = self.settings.api_key
        else:
            safe_params["apikey"] = self.settings.api_key
        try:
            response = await self._http.get(normalized_path, params=safe_params, headers=headers)
        except httpx.TimeoutException as exc:
            raise APMError("timeout", "Applications Manager request timed out.") from exc
        except httpx.ConnectError as exc:
            code = "tls_error" if _is_tls_error(exc) else "connection_error"
            raise APMError(code, "Unable to connect securely to Applications Manager.") from exc
        except httpx.HTTPError as exc:
            raise APMError("connection_error", "Unable to connect to Applications Manager.") from exc
        if response.status_code == 401:
            raise APMError("authentication_error", "Applications Manager authentication failed.")
        if response.status_code == 403:
            raise APMError("authorization_error", "Applications Manager denied the request.")
        if response.status_code == 404:
            raise APMError("not_found", "The requested Applications Manager resource was not found.")
        if response.is_error:
            raise APMError("upstream_error", f"Applications Manager returned HTTP {response.status_code}.")
        return response


def _is_tls_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, ssl.SSLError) or "certificate verify failed" in str(current).lower():
            return True
        current = current.__cause__ or current.__context__
    return False


def _xml_node(element: Any) -> dict[str, Any]:
    result: dict[str, Any] = dict(element.attrib)
    children = list(element)
    if children:
        for child in children:
            value = _xml_node(child)
            current = result.get(child.tag)
            if current is None:
                result[child.tag] = value
            elif isinstance(current, list):
                current.append(value)
            else:
                result[child.tag] = [current, value]
    text = (element.text or "").strip()
    if text:
        result["value"] = text
    return result
