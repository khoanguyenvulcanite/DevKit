import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from mcp.server.fastmcp import FastMCP
from starlette.responses import Response
import uvicorn

from src.utils.restAPI import ApiClientError, RestClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
http_logger = logging.getLogger("mcp-debug")


class MCPServer:
    def __init__(self, name: str = "GitHub MCP Server") -> None:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN not found in environment")

        self.mcp = FastMCP(name, 
                           stateless_http=True,
                           json_response=True)
        self.client = RestClient(
            base_url="https://api.github.com",
            token=token,
            timeout=(5, 30),
        )

        self.client.client.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

        self._register_tools()

    def _register_tools(self) -> None:
        @self.mcp.tool()
        async def get_all_repos() -> list[dict[str, Any]]:
            """Get repositories for the authenticated GitHub user."""
            return await self.get_all_repos()

        @self.mcp.tool()
        async def get_open_prs(repo: str) -> list[dict[str, Any]]:
            """Get open pull requests for a repository.

            Args:
                repo: Repository full name, e.g. "owner/repo"
            """
            return await self.get_open_prs(repo)

        @self.mcp.tool()
        async def get_pr_diff(repo: str, pr_number: int) -> str:
            """Get raw unified diff text for a pull request.

            Args:
                repo: Repository full name, e.g. "owner/repo"
                pr_number: Pull request number
            """
            return await self.get_pr_diff(repo, pr_number)
        
        @self.mcp.tool()
        async def review_pr_tool(command: str) -> str:
            """Parse slash-command input and fetch PR diff."""
            return await self.review_pr_tool(command)
        

    @staticmethod
    def _split_repo(repo: str) -> tuple[str, str]:
        parts = repo.strip().split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError('repo must be in the format "owner/repo"')
        return parts[0], parts[1]

    async def get_all_repos(self) -> list[dict[str, Any]]:
        repos = await self.client.get(
            "/user/repos",
            params={"per_page": 100, "sort": "updated"},
        )

        if not isinstance(repos, list):
            raise ApiClientError("Unexpected response format from /user/repos")

        return [
            {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "owner": repo["owner"]["login"],
                "private": repo["private"],
                "default_branch": repo["default_branch"],
                "url": repo["html_url"],
            }
            for repo in repos
        ]

    async def get_open_prs(self, repo: str) -> list[dict[str, Any]]:
        owner, repo_name = self._split_repo(repo)

        prs = await self.client.get(
            f"/repos/{owner}/{repo_name}/pulls",
            params={"state": "open", "per_page": 100},
        )

        if not isinstance(prs, list):
            raise ApiClientError("Unexpected response format from pull request list")

        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": pr["user"]["login"],
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "url": pr["html_url"],
            }
            for pr in prs
        ]

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        owner, repo_name = self._split_repo(repo)

        diff_text = await self.client.get(
            f"/repos/{owner}/{repo_name}/pulls/{pr_number}",
            headers={
                "Accept": "application/vnd.github.v3.diff",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        if not isinstance(diff_text, str):
            raise ApiClientError("Expected raw diff text but got non-text response")

        return diff_text


    async def review_pr_tool(self,command: str) -> str:
        """Parse slash-command input and fetch PR diff."""
        raw = command.strip()

        repo = None
        pr_number = None

        if "#" in raw and "repo=" not in raw:
            repo, pr_str = raw.split("#", 1)
            repo = repo.strip()
            pr_number = int(pr_str.strip())
        else:
            parts = raw.split()
            for part in parts:
                if part.startswith("repo="):
                    repo = part[len("repo="):].strip()
                elif part.startswith("pr_number="):
                    pr_number = int(part[len("pr_number="):].strip())

        if not repo:
            raise ValueError('Missing repo. Use repo=owner/repo or owner/repo#123')
        if pr_number is None:
            raise ValueError('Missing pr_number. Use pr_number=<number> or owner/repo#123')

        return await self.get_pr_diff(repo, pr_number)

    async def aclose(self) -> None:
        await self.client.aclose()

    def run_stdio(self) -> None:
        self.mcp.run(transport="stdio")


server = MCPServer("GitHub MCP Server")
app = FastAPI()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()

    interesting_headers = {
        k.lower(): v
        for k, v in request.headers.items()
        if k.lower() in {
            "accept",
            "content-type",
            "mcp-session-id",
            "user-agent",
        }
    }

    http_logger.info(">>> %s %s", request.method, request.url.path)
    http_logger.info(">>> headers=%s", interesting_headers)

    if body:
        try:
            http_logger.info(">>> body=%s", body.decode("utf-8"))
        except Exception:
            http_logger.info(">>> body=<binary %d bytes>", len(body))
    else:
        http_logger.info(">>> body=<empty>")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    cloned_request = Request(request.scope, receive)
    response = await call_next(cloned_request)

    http_logger.info("<<< status=%s", response.status_code)
    if "mcp-session-id" in response.headers:
        http_logger.info("<<< mcp-session-id=%s", response.headers["mcp-session-id"])

    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# mount MCP app at /mcp
app.mount("/mcp", server.mcp.streamable_http_app())


def main():
    server = MCPServer("GitHub MCP Server")
    server.mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()