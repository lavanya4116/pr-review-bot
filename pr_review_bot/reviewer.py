from groq import Groq
from pr_review_bot.config import GROQ_API_KEY, GROQ_MODEL
from pr_review_bot.github_client import PRInfo, GitHubClient

# System prompt — this shapes the entire review quality
SYSTEM_PROMPT = """You are a senior software engineer with 10+ years of experience 
doing thorough, constructive code reviews. You have deep expertise in:
- Security vulnerabilities and best practices
- Performance optimization and scalability  
- Clean code principles and maintainability
- Common bugs and edge cases

When reviewing code, you:
- Are specific and actionable, not vague
- Prioritize issues by severity (Critical/Warning/Suggestion)
- Explain WHY something is a problem, not just WHAT is wrong
- Acknowledge good practices when you see them
- Keep feedback professional and constructive

Format your review in clean markdown."""


def build_review_prompt(pr_info: PRInfo, diff: str) -> str:
    """
    Build the user prompt for the LLM.
    Good prompt structure = good review output.
    """
    # Count reviewable files
    reviewable = [f for f in pr_info.files if f.patch]

    prompt = f"""Please review this Pull Request:

**PR:** #{pr_info.number} — {pr_info.title}
**Author:** @{pr_info.author}
**Branch:** `{pr_info.head_branch}` → `{pr_info.base_branch}`
**Description:** {pr_info.description}
**Scale:** {pr_info.total_additions} additions, {pr_info.total_deletions} deletions across {len(reviewable)} files

---

{diff}

---

Provide a structured code review with these sections:

## 📋 Summary
Brief 2-3 sentence overview of what this PR does and your overall impression.

## 🔴 Critical Issues
Bugs, security vulnerabilities, or breaking changes that MUST be fixed.
If none, write "None found."

## 🟡 Warnings  
Performance issues, bad practices, or potential problems worth addressing.
If none, write "None found."

## 💡 Suggestions
Nice-to-have improvements, style issues, or minor refactors.
If none, write "None found."

## ✅ Positives
What was done well in this PR.

## 🏁 Verdict
One of: APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION
Followed by one sentence explaining your verdict."""

    return prompt


class PRReviewer:

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.github = GitHubClient()

    def review_pr(self, pr_info: PRInfo) -> str:
        """
        Send PR diff to Groq Llama 3 and get back a structured review.
        Returns the review text.
        """
        # Format the diff for the LLM
        diff = self.github.format_diff_for_review(pr_info)

        # Truncate if too long — Llama 3 has 8192 token context window
        # ~4 chars per token, so 6000 tokens ≈ 24000 chars — safe limit
        MAX_DIFF_CHARS = 24000
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS]
            diff += "\n\n[... diff truncated — showing first 24000 chars ...]"

        # Build the prompt
        prompt = build_review_prompt(pr_info, diff)

        # Call Groq API
        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,      # lower = more consistent, focused output
            max_tokens=2048,      # enough for a thorough review
        )

        review_text = response.choices[0].message.content
        return review_text

    def get_usage_stats(self, pr_info: PRInfo) -> dict:
        """
        Estimate token usage before making the API call.
        Useful for large PRs.
        """
        diff = self.github.format_diff_for_review(pr_info)
        prompt = build_review_prompt(pr_info, diff)

        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = len(prompt) // 4

        return {
            "estimated_input_tokens": estimated_tokens,
            "diff_chars": len(diff),
            "files": len(pr_info.files),
            "reviewable_files": len([f for f in pr_info.files if f.patch])
        }