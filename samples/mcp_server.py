import hmac
import json
import logging
import os

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from network_probe import run_probe


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lab-mcp")
hostname = os.environ["MCP_HOSTNAME"]
mcp = FastMCP(
    "closed-network-lab",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", hostname, f"{hostname}:443"],
        allowed_origins=[f"https://{hostname}"],
    ),
)


@mcp.tool()
def read_private_marker() -> str:
    """Read the current lab marker from private Blob and PostgreSQL and return evidence."""
    result = run_probe()
    logger.info("Completed private data probe: %s", json.dumps(result))
    return json.dumps(result)


@mcp.tool()
def read_private_marker_with_files() -> str:
    """Read the lab marker from private Blob, PostgreSQL, and Azure Files."""
    result = run_probe(include_files=True)
    logger.info("Completed private data probe with Files: %s", json.dumps(result))
    return json.dumps(result)


class LabTokenMiddleware:
    def __init__(self, app):
        self.app = app
        self.token = os.environ["MCP_LAB_TOKEN"]
        if len(self.token) < 32:
            raise ValueError("MCP_LAB_TOKEN must be at least 32 characters")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        supplied = headers.get(b"x-lab-tool-token", b"")
        if not hmac.compare_digest(supplied, self.token.encode("utf-8")):
            logger.warning("Rejected MCP request without a valid lab token")
            await send(
                {"type": "http.response.start", "status": 401,
                 "headers": [(b"content-type", b"text/plain")]}
            )
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return
        await self.app(scope, receive, send)


app = LabTokenMiddleware(mcp.streamable_http_app())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
