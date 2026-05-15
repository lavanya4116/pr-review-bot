# test_github.py — delete after testing
from pr_review_bot.github_client import GitHubClient

client = GitHubClient()

# Use any real public repo and PR number
# Find one at: github.com/any-public-repo/pulls
owner, repo = client.parse_repo("fastapi/fastapi")
pr_info = client.get_pr_info(owner, repo, 1)   # PR #1 of fastapi repo

print(f"Title: {pr_info.title}")
print(f"Author: {pr_info.author}")
print(f"Files changed: {len(pr_info.files)}")
print(f"Total additions: {pr_info.total_additions}")
print(f"Total deletions: {pr_info.total_deletions}")
print("\nFiles:")
for f in pr_info.files:
    print(f"  {f.status}: {f.filename} (+{f.additions} -{f.deletions})")

print("\n--- FORMATTED DIFF (first 500 chars) ---")
diff = client.format_diff_for_review(pr_info)
print(diff[:500])