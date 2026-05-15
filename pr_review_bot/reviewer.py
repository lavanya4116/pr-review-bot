import time
from groq import Groq
from groq import APITimeoutError, APIConnectionError, RateLimitError
from pr_review_bot.config import GROQ_API_KEY, GROQ_MODEL
from pr_review_bot.github_client import PRInfo, GitHubClient
from pr_review_bot.exceptions import LLMError, LLMTimeoutError

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

    def review_pr(self, pr_info: PRInfo, max_retries: int = 2) -> str:
        """
        Send PR diff to Groq Llama 3 and get back a structured review.
        Retries on transient failures.
        """
        diff = self.github.format_diff_for_review(pr_info)

        # Truncate if too long
        MAX_DIFF_CHARS = 24000
        truncated = False
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS]
            diff += "\n\n[... diff truncated — showing first 24000 chars ...]"
            truncated = True

        prompt = build_review_prompt(pr_info, diff)

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                    timeout=30      # 30 second timeout
                )

                review_text = response.choices[0].message.content

                # Add truncation notice if diff was cut
                if truncated:
                    review_text += (
                        "\n\n---\n"
                        "⚠️ *Note: PR diff was truncated due to size. "
                        "Review covers the first 24,000 characters of changes.*"
                    )

                return review_text

            except APITimeoutError:
                last_error = LLMTimeoutError(
                    "❌ Groq API timed out after 30 seconds.\n"
                    "Try again — Groq is usually fast but occasionally slow."
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue

            except RateLimitError:
                raise LLMError(
                    "❌ Groq API rate limit exceeded.\n"
                    "Wait a minute and try again. "
                    "Free tier allows ~30 requests/minute."
                )

            except APIConnectionError:
                last_error = LLMError(
                    "❌ Cannot connect to Groq API.\n"
                    "Check your internet connection."
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue

            except Exception as e:
                raise LLMError(f"❌ Unexpected LLM error: {str(e)}")

        raise last_error

    def get_usage_stats(self, pr_info: PRInfo) -> dict:
        diff = self.github.format_diff_for_review(pr_info)
        prompt = build_review_prompt(pr_info, diff)

        estimated_tokens = len(prompt) // 4

        return {
            "estimated_input_tokens": estimated_tokens,
            "diff_chars": len(diff),
            "files": len(pr_info.files),
            "reviewable_files": len([f for f in pr_info.files if f.patch])
        }