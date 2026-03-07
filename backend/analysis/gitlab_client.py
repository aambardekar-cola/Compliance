"""GitLab API v4 client for PCO codebase access."""
import hashlib
import json
import logging
from typing import Optional

import boto3
import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)

# File extensions relevant to PACE EHR compliance analysis
RELEVANT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".sql", ".yaml", ".yml",
    ".json", ".html", ".css", ".env", ".cfg", ".ini", ".toml",
}

# Directories to exclude from analysis
EXCLUDED_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".venv", "venv", ".tox", ".pytest_cache", "coverage",
    "vendor", "static", "migrations",
}

# Max file size in bytes to fetch (skip large files)
MAX_FILE_SIZE = 100_000  # 100 KB


class GitLabClient:
    """Wrapper around GitLab REST API v4 for codebase analysis.

    Credentials are resolved in this order:
    1. Explicit parameters passed to the constructor
    2. IntegrationConfig record from the database
    3. Environment variables (GITLAB_URL, GITLAB_TOKEN)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        project_ids: Optional[list[int]] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.gitlab_url).rstrip("/")
        self.token = token or settings.gitlab_token
        self.project_ids = project_ids or settings.gitlab_project_id_list
        self._client: Optional[httpx.AsyncClient] = None

    # ---- HTTP helpers ----

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialise the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.base_url}/api/v4",
                headers={
                    "PRIVATE-TOKEN": self.token,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        """Make an authenticated request to the GitLab API."""
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _paginate(self, path: str, params: dict | None = None) -> list:
        """Fetch all pages of a paginated GitLab endpoint."""
        params = params or {}
        params.setdefault("per_page", 100)
        all_items: list = []
        page = 1

        while True:
            params["page"] = page
            client = await self._get_client()
            response = await client.get(path, params=params)
            response.raise_for_status()
            items = response.json()

            if not items:
                break

            all_items.extend(items)
            total_pages = int(response.headers.get("x-total-pages", page))
            if page >= total_pages:
                break
            page += 1

        return all_items

    # ---- Public API ----

    async def test_connection(self) -> dict:
        """Verify connectivity and token validity.

        Returns:
            Dict with connection status and user info.
        """
        try:
            user = await self._request("GET", "/user")
            return {
                "status": "connected",
                "username": user.get("username"),
                "name": user.get("name"),
                "email": user.get("email"),
            }
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def list_projects(self) -> list[dict]:
        """List configured projects with basic info."""
        projects = []
        for pid in self.project_ids:
            try:
                proj = await self._request("GET", f"/projects/{pid}")
                projects.append({
                    "id": proj["id"],
                    "name": proj["name"],
                    "path_with_namespace": proj["path_with_namespace"],
                    "default_branch": proj.get("default_branch", "main"),
                    "web_url": proj.get("web_url"),
                    "last_activity_at": proj.get("last_activity_at"),
                })
            except Exception as e:
                logger.warning(f"Failed to fetch project {pid}: {e}")
                projects.append({"id": pid, "error": str(e)})
        return projects

    async def get_repository_tree(
        self,
        project_id: int,
        ref: str = "main",
        path: str = "",
        recursive: bool = True,
    ) -> list[dict]:
        """Fetch the file tree of a repository.

        Args:
            project_id: GitLab project ID
            ref: Branch or tag name
            path: Subdirectory to list (empty = root)
            recursive: If True, return all files recursively

        Returns:
            List of file/dir entries: [{type, path, name, id}]
        """
        params = {
            "ref": ref,
            "recursive": str(recursive).lower(),
        }
        if path:
            params["path"] = path

        tree = await self._paginate(
            f"/projects/{project_id}/repository/tree",
            params=params,
        )
        return tree

    async def get_file_content(
        self,
        project_id: int,
        file_path: str,
        ref: str = "main",
    ) -> Optional[str]:
        """Fetch raw content of a single file.

        Args:
            project_id: GitLab project ID
            file_path: Path relative to repo root
            ref: Branch or tag name

        Returns:
            File content as a string, or None on error.
        """
        try:
            import urllib.parse
            encoded_path = urllib.parse.quote(file_path, safe="")
            client = await self._get_client()
            response = await client.get(
                f"/projects/{project_id}/repository/files/{encoded_path}/raw",
                params={"ref": ref},
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"File not found: {file_path}")
            else:
                logger.warning(f"Error fetching {file_path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching {file_path}: {e}")
            return None

    async def search_files(
        self,
        project_id: int,
        query: str,
        ref: str = "main",
    ) -> list[dict]:
        """Search file contents across the repository.

        Returns:
            List of search results with file path and matched lines.
        """
        try:
            results = await self._paginate(
                f"/projects/{project_id}/search",
                params={
                    "scope": "blobs",
                    "search": query,
                    "ref": ref,
                },
            )
            return [
                {
                    "file_path": r.get("filename"),
                    "project_id": r.get("project_id", project_id),
                    "data": r.get("data", ""),
                    "startline": r.get("startline"),
                    "ref": ref,
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Search failed for project {project_id}: {e}")
            return []

    async def get_relevant_files(
        self,
        project_id: int,
        ref: str = "main",
    ) -> list[dict]:
        """Fetch the repo tree filtered to relevant source files only.

        Excludes test files, vendored deps, and binary/large files.
        """
        tree = await self.get_repository_tree(project_id, ref=ref)

        relevant = []
        for entry in tree:
            if entry.get("type") != "blob":
                continue

            file_path = entry.get("path", "")

            # Check excluded directories
            parts = file_path.split("/")
            if any(part in EXCLUDED_DIRS for part in parts):
                continue

            # Check extension
            ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
            if ext not in RELEVANT_EXTENSIONS:
                continue

            # Skip test files
            basename = parts[-1].lower()
            if basename.startswith("test_") or basename.endswith("_test.py"):
                continue

            relevant.append({
                "path": file_path,
                "name": entry.get("name"),
                "id": entry.get("id"),
            })

        logger.info(
            f"Project {project_id}: {len(relevant)} relevant files "
            f"out of {len(tree)} total entries"
        )
        return relevant

    # ---- S3 Caching ----

    async def cache_snapshot(
        self,
        project_id: int,
        files_with_content: list[dict],
    ) -> str:
        """Cache a codebase snapshot in S3.

        Args:
            project_id: GitLab project ID
            files_with_content: List of {path, content} dicts

        Returns:
            S3 key of the cached snapshot.
        """
        settings = get_settings()
        if not settings.documents_bucket:
            logger.debug("No S3 bucket configured — skipping cache")
            return ""

        # Create a hash-based key for deduplication
        content_hash = hashlib.sha256(
            json.dumps(
                [f["path"] for f in files_with_content], sort_keys=True
            ).encode()
        ).hexdigest()[:12]

        s3_key = f"codebase-snapshots/{project_id}/{content_hash}.json"

        try:
            s3 = boto3.client("s3")
            s3.put_object(
                Bucket=settings.documents_bucket,
                Key=s3_key,
                Body=json.dumps(files_with_content, default=str),
                ContentType="application/json",
            )
            logger.info(f"Cached snapshot: s3://{settings.documents_bucket}/{s3_key}")
            return s3_key
        except Exception as e:
            logger.warning(f"Failed to cache snapshot: {e}")
            return ""
