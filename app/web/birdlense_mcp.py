"""
BirdLense Hub MCP server — экспортирует OpenAPI-эндпоинты как MCP-инструменты.
Запуск: python birdlense_mcp.py [--transport stdio|http|streamable-http] [--port 8001]
В контейнере: entrypoint запускает при mcp.enabled=true через streamable HTTP на /mcp.
Защита: mcp.token или MCP_TOKEN env. Пусто — без аутентификации.
"""

import argparse
import asyncio
import os

import httpx
import yaml

# app_config: PYTHONPATH=/app при запуске из entrypoint
from app_config.app_config import app_config

from fastmcp import FastMCP
from fastmcp.server.providers.openapi import RouteMap, MCPType

OPENAPI_PATH = os.path.join(os.path.dirname(__file__), "openapi.yaml")
with open(OPENAPI_PATH, "r") as f:
    birdlense_spec = yaml.safe_load(f)

for path, methods in birdlense_spec.get("paths", {}).items():
    for method, op in methods.items():
        if isinstance(op, dict):
            op["x-tool"] = True

custom_maps = [
    RouteMap(
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        pattern=r".*",
        mcp_type=MCPType.TOOL,
    )
]


def get_mcp_token() -> str:
    """Токен для доступа к MCP. Env MCP_TOKEN приоритетнее конфига."""
    return (os.environ.get("MCP_TOKEN") or app_config.get("mcp.token") or "").strip()


def get_api_base_url() -> str:
    """API URL для MCP-клиента (вызовы к BirdLense Hub)."""
    url = app_config.get("mcp.api_url") or os.environ.get("BIRDLENSE_API_URL", "")
    if url:
        return url.rstrip("/")
    # В контейнере gunicorn на 127.0.0.1:8000
    return "http://127.0.0.1:8000/api/ui"


def create_mcp_server() -> FastMCP:
    """Собрать FastMCP из openapi.yaml с HTTP-клиентом к Hub и опциональной проверкой токена."""
    api_url = get_api_base_url()
    token = get_mcp_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    client = httpx.AsyncClient(base_url=api_url, headers=headers, timeout=30.0)

    mcp_kwargs = dict(
        openapi_spec=birdlense_spec,
        client=client,
        name="BirdLense Hub",
        route_maps=custom_maps,
    )
    if token:
        from fastmcp.server.auth.providers.debug import DebugTokenVerifier

        verifier = DebugTokenVerifier(validate=lambda t: t == token)
        mcp_kwargs["auth"] = verifier

    return FastMCP.from_openapi(**mcp_kwargs)


async def check_mcp(mcp: FastMCP) -> None:
    """Вывести в stdout число tools/resources (режим ``--check``)."""
    tools = await mcp.get_tools()
    resources = await mcp.get_resources()
    templates = await mcp.get_resource_templates()
    print(f"BirdLense Hub MCP: {len(tools)} tools, {len(resources)} resources, {len(templates)} templates")
    if tools:
        print(f"  Tools: {', '.join(list(tools.keys())[:8])}{'...' if len(tools) > 8 else ''}")


def main() -> None:
    """CLI: stdio или HTTP transport для MCP-сервера."""
    parser = argparse.ArgumentParser(description="BirdLense Hub MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        default="stdio",
        help="Transport: stdio (default) or streamable-http (container/web). 'http' is kept as alias.",
    )
    parser.add_argument("--port", type=int, default=8001, help="Port for HTTP transport")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transport")
    parser.add_argument("--check", action="store_true", help="Only check tools and exit")
    args = parser.parse_args()

    mcp = create_mcp_server()

    if args.check:
        asyncio.run(check_mcp(mcp))
        return

    if args.transport in ("http", "streamable-http"):
        auth_status = "protected" if get_mcp_token() else "no auth"
        print(f"BirdLense Hub MCP HTTP: http://{args.host}:{args.port}/mcp ({auth_status})")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
