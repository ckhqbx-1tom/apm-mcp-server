#!/usr/bin/env python3
"""Exercise initialize and tools/list over a real localhost MCP SSE socket."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys

from mcp import ClientSession
from mcp.client.sse import sse_client

from smoke_test import validate_tools


def _unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _wait_until_listening(port: int, process: subprocess.Popen[bytes]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("MCP SSE server exited before accepting connections.")
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.05)
        else:
            writer.close()
            await writer.wait_closed()
            return
    raise TimeoutError("MCP SSE server did not start within five seconds.")


async def smoke_test() -> None:
    port = _unused_port()
    environment = os.environ.copy()
    environment.update({
        "APM_API_URL": "https://apm.invalid",
        "APM_API_KEY": "sse-smoke-placeholder",
        "APM_VERIFY_TLS": "true",
        "APM_MCP_READ_ONLY": "true",
        "APM_MCP_TRANSPORT": "sse",
        "APM_MCP_HOST": "127.0.0.1",
        "APM_MCP_PORT": str(port),
        "APM_MCP_SSE_PATH": "/sse",
        "APM_MCP_MESSAGE_PATH": "/messages/",
        "APM_LOG_LEVEL": "CRITICAL",
    })
    process = subprocess.Popen(
        [sys.executable, "-m", "apm_mcp.server"],
        cwd=os.getcwd(), env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        await _wait_until_listening(port, process)
        async with sse_client(
            f"http://127.0.0.1:{port}/sse", timeout=3, sse_read_timeout=10,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
        validate_tools(listed.tools, "SSE")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(smoke_test())
