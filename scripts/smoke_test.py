#!/usr/bin/env python3
"""Exercise the real MCP stdio lifecycle without contacting Applications Manager."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "GetAlarms",
    "GetAlarmDetails",
    "GetAlarmNotes",
    "SearchMonitors",
    "ListMonitors",
    "GetMonitorSummary",
    "GetServerContext",
    "GetMonitorRelationships",
    "GetMonitorGroupTopology",
    "ListMonitorMetrics",
    "GetPerformanceMetrics",
}
FORBIDDEN_SCHEMA_TERMS = {"apikey", "api_key", "password", "token", "authorization"}


async def smoke_test(docker_image: str | None = None) -> None:
    environment = os.environ.copy()
    environment.update({
        "APM_API_URL": "https://apm.invalid",
        "APM_API_KEY": "stdio-smoke-placeholder",
        "APM_VERIFY_TLS": "true",
        "APM_MCP_READ_ONLY": "true",
        "APM_LOG_LEVEL": "CRITICAL",
    })
    if docker_image:
        parameters = StdioServerParameters(
            command="docker",
            args=[
                "run", "--rm", "-i", "--cap-drop=ALL",
                "-e", "APM_API_URL=https://apm.invalid",
                "-e", "APM_API_KEY=stdio-smoke-placeholder",
                "-e", "APM_VERIFY_TLS=true",
                "-e", "APM_MCP_READ_ONLY=true",
                "-e", "APM_LOG_LEVEL=CRITICAL",
                docker_image,
            ],
            env=os.environ.copy(),
            cwd=os.getcwd(),
        )
    else:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "apm_mcp.server"],
            env=environment,
            cwd=os.getcwd(),
        )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()

    names = {tool.name for tool in listed.tools}
    if names != EXPECTED_TOOLS:
        raise AssertionError(f"Unexpected MCP tool set: {sorted(names)}")
    schemas = json.dumps([tool.inputSchema for tool in listed.tools]).lower()
    found = sorted(term for term in FORBIDDEN_SCHEMA_TERMS if term in schemas)
    if found:
        raise AssertionError(f"Forbidden terms in MCP tool schemas: {found}")
    print(f"MCP stdio smoke test passed: {len(names)} read-only tools")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker-image", help="Run the stdio server from this Docker image.")
    arguments = parser.parse_args()
    asyncio.run(smoke_test(arguments.docker_image))
