import requests
from dataclasses import dataclass
from typing import Optional
from pr_review_bot.config import GITHUB_TOKEN

# Base URL for all GitHub API calls
GITHUB_API_BASE = "https://api.github.com"


@dataclass
class PRFile:
    """Represents a single changed file in a PR"""
    filename: str
    status: str          # added, modified, removed, renamed
    additions: int
    deletions: int
    patch: Optional[str] # the actual diff — None if file is binary


@dataclass
class PRInfo:
    """All the info we need about a PR to review it"""
    number: int
    title: str
    author: str
    description: str
    base_branch: str     # branch being merged INTO
    head_branch: str     # branch with new changes
    files: list[PRFile]
    total_additions: int
    total_deletions: int


class GitHubClient:
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        })

    def _get(self, url: str) -> dict:
        """Make a GET request, handle errors cleanly"""
        response = self.session.get(url)

        if response.status_code == 401:
            raise ValueError(
                "❌ GitHub token is invalid or expired.\n"
                "Generate a new token at: github.com/settings/tokens"
            )
        if response.status_code == 404:
            raise ValueError(
                "❌ PR or repo not found. Check:\n"
                "  • Repo format is 'owner/reponame' e.g. 'torvalds/linux'\n"
                "  • PR number exists\n"
                "  • Your token has 'repo' scope for private repos"
            )
        if response.status_code == 403:
            raise ValueError(
                "❌ Rate limited by GitHub API.\n"
                "Wait a minute and try again."
            )

        response.raise_for_status()
        return response.json()

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """Fetch everything we need about a PR"""

        # Step 1: Get PR metadata
        pr_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
        pr_data = self._get(pr_url)

        # Step 2: Get changed files with diffs
        files_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        files_data = self._get(files_url)

        # Step 3: Parse files into our dataclass
        files = []
        for f in files_data:
            files.append(PRFile(
                filename=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch")    # .get() because binary files have no patch
            ))

        return PRInfo(
            number=pr_data["number"],
            title=pr_data["title"],
            author=pr_data["user"]["login"],
            description=pr_data.get("body") or "No description provided",
            base_branch=pr_data["base"]["ref"],
            head_branch=pr_data["head"]["ref"],
            files=files,
            total_additions=pr_data["additions"],
            total_deletions=pr_data["deletions"]
        )

    def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str
    ) -> dict:
        """Post a review comment on the PR"""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

        payload = {
            "body": body,
            "event": "COMMENT"      # COMMENT, APPROVE, or REQUEST_CHANGES
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def format_diff_for_review(self, pr_info: PRInfo) -> str:
        """
        Format the PR diff into a clean string for the LLM.
        This is important — LLMs work better with well-structured input.
        """
        parts = []

        parts.append(f"PR Title: {pr_info.title}")
        parts.append(f"Author: {pr_info.author}")
        parts.append(f"Branch: {pr_info.head_branch} → {pr_info.base_branch}")
        parts.append(f"Description: {pr_info.description}")
        parts.append(f"Changes: +{pr_info.total_additions} -{pr_info.total_deletions} lines")
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

            parts.append("")    # blank line between files

        return "\n".join(parts)

    def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT"
    ) -> dict:
        """
        Post a formal PR review.
        event options:
          COMMENT         → just a comment, no approval decision
          APPROVE         → approves the PR
          REQUEST_CHANGES → requests changes before merge
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

        payload = {
            "body": body,
            "event": event
        }

        response = self.session.post(url, json=payload)

        if response.status_code == 422:
            raise ValueError(
                "❌ Cannot post review — you may be trying to review "
                "your own PR. GitHub doesn't allow self-reviews.\n"
                "Try posting as an issue comment instead with --comment flag."
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
        """
        Post a regular comment on a PR (via issues API).
        Works even on your own PRs — good fallback.
        """
        # PRs and issues share the same comment API in GitHub
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        payload = {"body": body}

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_existing_bot_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> list:
        """
        Check if bot has already commented on this PR.
        Avoids spamming duplicate reviews.
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        comments = self._get(url)

        # Filter comments that look like they're from our bot
        bot_comments = [
            c for c in comments
            if "🤖 Automated PR Review" in c.get("body", "")
        ]

        return bot_comments
    
    @staticmethod
    def parse_repo(repo_string: str) -> tuple[str, str]:
        """
        Parse 'owner/repo' string into (owner, repo) tuple.
        Handles edge cases like full GitHub URLs.
        """
        # Handle full URLs like https://github.com/owner/repo
        if "github.com" in repo_string:
            repo_string = repo_string.split("github.com/")[-1]

        # Remove trailing slashes
        repo_string = repo_string.strip("/")

        parts = repo_string.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"❌ Invalid repo format: '{repo_string}'\n"
                f"Expected format: 'owner/reponame' e.g. 'torvalds/linux'"
            )

        return parts[0], parts[1]