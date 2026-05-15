import requests
import time
from dataclasses import dataclass
from typing import Optional
from pr_review_bot.config import GITHUB_TOKEN
from pr_review_bot.exceptions import (
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubError
)

GITHUB_API_BASE = "https://api.github.com"
MAX_RETRIES = 3
RETRY_DELAY = 2     # seconds between retries


@dataclass
class PRFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: Optional[str]


@dataclass
class PRInfo:
    number: int
    title: str
    author: str
    description: str
    base_branch: str
    head_branch: str
    files: list[PRFile]
    total_additions: int
    total_deletions: int
    state: str          # open, closed, merged


class GitHubClient:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        })

    def _get(self, url: str, retries: int = MAX_RETRIES) -> dict:
        """
        GET request with automatic retry on transient failures.
        Raises specific exceptions for different error types.
        """
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)

                if response.status_code == 401:
                    raise GitHubAuthError(
                        "❌ GitHub token is invalid or expired.\n"
                        "Generate a new token at: github.com/settings/tokens"
                    )

                if response.status_code == 404:
                    raise GitHubNotFoundError(
                        "❌ PR or repo not found. Check:\n"
                        "  • Format is 'owner/reponame' e.g. 'tiangolo/fastapi'\n"
                        "  • PR number exists\n"
                        "  • Token has 'repo' scope for private repos"
                    )

                if response.status_code == 403:
                    # Check if it's rate limiting
                    if "rate limit" in response.text.lower():
                        reset_time = response.headers.get(
                            "X-RateLimit-Reset", "unknown"
                        )
                        raise GitHubRateLimitError(
                            f"❌ GitHub API rate limit exceeded.\n"
                            f"Resets at: {reset_time}\n"
                            f"Wait a minute and try again."
                        )
                    raise GitHubError(
                        "❌ GitHub API forbidden. Check your token permissions."
                    )

                # Retry on server errors (5xx)
                if response.status_code >= 500:
                    if attempt < retries - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    raise GitHubError(
                        f"❌ GitHub API server error ({response.status_code}). "
                        f"Try again later."
                    )

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise GitHubError(
                    "❌ GitHub API timed out. Check your internet connection."
                )

            except requests.exceptions.ConnectionError:
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise GitHubError(
                    "❌ Cannot connect to GitHub. Check your internet connection."
                )

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """Fetch everything we need about a PR"""

        pr_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        pr_data = self._get(pr_url)

        files_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        files_data = self._get(files_url)

        files = []
        for f in files_data:
            files.append(PRFile(
                filename=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch")
            ))

        # Determine state — open, closed, or merged
        state = pr_data["state"]
        if pr_data.get("merged_at"):
            state = "merged"

        return PRInfo(
            number=pr_data["number"],
            title=pr_data["title"],
            author=pr_data["user"]["login"],
            description=pr_data.get("body") or "No description provided",
            base_branch=pr_data["base"]["ref"],
            head_branch=pr_data["head"]["ref"],
            files=files,
            total_additions=pr_data["additions"],
            total_deletions=pr_data["deletions"],
            state=state
        )

    def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT"
    ) -> dict:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {"body": body, "event": event}
        response = self.session.post(url, json=payload, timeout=10)

        if response.status_code == 422:
            raise GitHubError(
                "❌ Cannot post review — GitHub doesn't allow self-reviews.\n"
                "Use --comment flag to post as an issue comment instead."
            )

        response.raise_for_status()
        return response.json()

    def post_issue_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str
    ) -> dict:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}
        response = self.session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_existing_bot_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> list:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        comments = self._get(url)
        return [
            c for c in comments
            if "🤖 Automated PR Review" in c.get("body", "")
        ]

    def format_diff_for_review(self, pr_info: PRInfo) -> str:
        parts = []
        parts.append(f"PR Title: {pr_info.title}")
        parts.append(f"Author: {pr_info.author}")
        parts.append(f"Branch: {pr_info.head_branch} → {pr_info.base_branch}")
        parts.append(f"Description: {pr_info.description}")
        parts.append(
            f"Changes: +{pr_info.total_additions} -{pr_info.total_deletions} lines"
        )
        parts.append("\n" + "="*60 + "\n")

        for file in pr_info.files:
            parts.append(f"File: {file.filename} ({file.status})")
            parts.append(f"+{file.additions} additions, -{file.deletions} deletions")

            if file.patch:
                parts.append("```diff")
                parts.append(file.patch)
                parts.append("```")
            else:
                parts.append("[Binary file — no diff available]")

            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def parse_repo(repo_string: str) -> tuple[str, str]:
        if "github.com" in repo_string:
            repo_string = repo_string.split("github.com/")[-1]

        repo_string = repo_string.strip("/")
        parts = repo_string.split("/")

        if len(parts) != 2:
            raise ValueError(
                f"❌ Invalid repo format: '{repo_string}'\n"
                f"Expected: 'owner/reponame' e.g. 'tiangolo/fastapi'"
            )

        return parts[0], parts[1]