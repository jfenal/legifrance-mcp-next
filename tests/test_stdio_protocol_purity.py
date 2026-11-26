"""Regression test for https://github.com/jfenal/legifrance-mcp/issues/16.

Spawns the real stdio entrypoint as a subprocess -- the only way to catch
this class of bug, since every other test in this suite mocks FastMCP
and never exercises a real byte-level stdout stream. stdout is the
JSON-RPC protocol channel under stdio transport: every line on it must
parse as JSON, never a stray log line. This is exactly the manual
verification that originally found the bug, now automated.
"""

import asyncio
import json
import os
import sys

import pytest

pytestmark = pytest.mark.asyncio


async def _send(proc: asyncio.subprocess.Process, message: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message).encode() + b"\n")
    await proc.stdin.drain()


async def _recv(proc: asyncio.subprocess.Process, timeout: float = 15.0) -> dict:
    assert proc.stdout is not None
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
    return json.loads(line)


@pytest.fixture
async def stdio_server(tmp_path):
    # Inherit the real environment (sys.executable already pins the venv
    # to use; python-dotenv's load_dotenv() will also pick up this repo's
    # own .env if one exists, which is harmless here since the only tool
    # call made in these tests, legifrance_report_discovery, never touches
    # PISTE) and override only what these tests actually care about.
    env = {**os.environ, "MCP_TRANSPORT_PROTOCOL": "stdio", "ENABLE_AUTH": "False"}
    log_file = tmp_path / "server.log"
    env["LOG_FILE_PATH"] = str(log_file)

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "legifrance_mcp.src.main",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        yield proc, log_file
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()


class TestStdioProtocolPurity:
    async def test_every_stdout_line_is_valid_json_rpc(self, stdio_server):
        proc, _ = stdio_server

        await _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        init_response = await _recv(proc)
        assert init_response["jsonrpc"] == "2.0"
        assert "result" in init_response

        await _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # A tool that doesn't need real PISTE credentials, and that itself
        # logs (logger.info("discovery_feedback", ...)) -- if logging ever
        # regresses back onto stdout, this call is where it would show up
        # as a non-JSON line interleaved with the real response.
        await _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "legifrance_report_discovery",
                    "arguments": {
                        "fond_types": ["code_article"],
                        "tools_used": ["rechercher_code"],
                        "action_sequence": ["test call"],
                        "outcome": "test outcome",
                    },
                },
            },
        )
        tool_response = await _recv(proc)
        assert tool_response["jsonrpc"] == "2.0"
        assert "result" in tool_response

    async def test_startup_logging_reaches_stderr_not_stdout(self, stdio_server):
        proc, _ = stdio_server

        # Give the process a moment to emit its startup log line, then
        # close stdin so it exits cleanly without needing a real request.
        await asyncio.sleep(1.0)
        assert proc.stdin is not None
        proc.stdin.close()

        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

        assert proc.stderr is not None
        stderr_output = (await proc.stderr.read()).decode()
        assert "Legifrance MCP Server initialized successfully" in stderr_output

    async def test_log_file_captures_startup_message(self, stdio_server):
        proc, log_file = stdio_server

        await asyncio.sleep(1.0)
        assert proc.stdin is not None
        proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

        assert log_file.exists()
        assert "Legifrance MCP Server initialized successfully" in log_file.read_text()
