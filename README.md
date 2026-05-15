# 🤖 PR Review Bot

An AI-powered CLI tool that reviews GitHub Pull Requests using 
Groq + Llama 3. Get structured code reviews in seconds, 
directly in your terminal or posted as GitHub comments.

```bash
review-bot review --repo tiangolo/fastapi --pr 100
```

## ✨ Demo

```
╭─────────────────────────────────────╮
│  🤖 PR Review Bot                   │
│  AI-powered reviews via Groq + Llama 3 │
╰─────────────────────────────────────╯

📋 Fetching PR #100 from tiangolo/fastapi...

┌──────────────┬────────────────────────────┐
│ 📌 Title     │ Fix dependency resolution  │
│ 👤 Author    │ @tiangolo                  │
│ 🔀 Branch    │ fix-deps → main            │
│ 📊 Changes   │ +42  -18                   │
│ 📁 Files     │ 3                          │
└──────────────┴────────────────────────────┘

🔍 Analyzing 3 files with Llama 3 on Groq...

╭──────────── ✨ AI Code Review ────────────╮
│                                           │
│ ## 📋 Summary                             │
│ This PR fixes dependency resolution...    │
│                                           │
│ ## 🔴 Critical Issues                     │
│ None found.                               │
│                                           │
│ ## 🟡 Warnings                            │
│ Version pinning may cause conflicts...    │
│                                           │
│ ## ✅ Positives                           │
│ Clean separation of concerns...           │
│                                           │
│ ## 🏁 Verdict                             │
│ APPROVE — minor warning worth noting      │
╰───────────────────────────────────────────╯
```

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| CLI | Python + Click | Subcommands, flags, auto-help generation |
| GitHub | REST API v3 | Fetch diffs, post reviews, detect duplicates |
| LLM | Groq + Llama 3 (70B) | Free, fastest inference available, open weights |
| Output | Rich | Professional terminal UI — tables, panels, colors |
| Resilience | Retry + backoff | Handles transient failures gracefully |

## 🚀 Installation

```bash
git clone https://github.com/YOUR_USERNAME/pr-review-bot
cd pr-review-bot
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

### Get API Keys (both free)

**GitHub Token:**
1. GitHub → Settings → Developer Settings → Personal Access Tokens
2. Generate token with `repo` scope

**Groq API Key:**
1. Sign up free at [console.groq.com](https://console.groq.com)
2. Create API key — no credit card needed

```bash
cp .env.example .env
# Add your keys to .env
```

## 📡 Commands

### Review a PR
```bash
# Print review to terminal
review-bot review --repo owner/repo --pr 42

# Post review as GitHub comment
review-bot review --repo owner/repo --pr 42 --post

# Post on your own PRs (issue comment)
review-bot review --repo owner/repo --pr 42 --post --comment

# Save review to file
review-bot review --repo owner/repo --pr 42 --save review.md

# Show full diff being sent to LLM
review-bot review --repo owner/repo --pr 42 --verbose
```

### Other Commands
```bash
# Check PR stats without reviewing
review-bot stats --repo owner/repo --pr 42

# Verify your API keys are configured
review-bot config
```

## 🧠 Design Decisions

**Why Groq over OpenAI?**
Groq runs Llama 3 on custom LPU hardware — typically 2-3x faster than 
OpenAI for inference with a generous free tier. For a CLI tool where 
the user is waiting, latency matters. Open-weights model also means 
code review data isn't used to train proprietary models.

**Why structured prompts?**
The system prompt sets the reviewer persona — senior engineer, 
specific expertise areas, output format. The user prompt enforces 
specific sections (Critical/Warnings/Suggestions). Structured input 
gives consistent, parseable output instead of free-form text.

**Duplicate detection before API call**
Bot checks for existing reviews before calling the LLM — avoids 
wasting API calls and spamming PRs. Use `--force` to override.

**Retry with backoff**
Network errors and 5xx responses retry up to 3 times with increasing 
delays. Auth errors and 404s fail immediately — retrying won't help.

**Self-review limitation**
GitHub API rejects self-reviews (422). Handled gracefully with 
`--comment` flag fallback using the Issues API instead.

## ⚡ Performance

| Metric | Value |
|--------|-------|
| Avg review time | ~2-3 seconds |
| Max diff size | 24,000 chars (~6k tokens) |
| GitHub API calls per review | 2-3 |
| Rate limit | 30 Groq req/min (free tier) |

## 🗂️ Project Structure

```
pr_review_bot/
├── cli.py            # Click commands — entry point
├── github_client.py  # GitHub REST API calls
├── reviewer.py       # Groq LLM integration + prompt engineering
├── formatter.py      # GitHub comment formatting
├── config.py         # Environment variable loading
└── exceptions.py     # Custom exception hierarchy
```