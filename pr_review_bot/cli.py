import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.live import Live
from rich import print as rprint
from pr_review_bot.config import validate_config
from pr_review_bot.github_client import GitHubClient
from pr_review_bot.reviewer import PRReviewer
from rich.markdown import Markdown

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]🤖 PR Review Bot[/bold cyan]\n"
        "[dim]AI-powered code reviews using Groq + Llama 3[/dim]",
        border_style="cyan"
    ))


def print_pr_summary(pr_info):
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("📌 Title", pr_info.title)
    table.add_row("👤 Author", f"@{pr_info.author}")
    table.add_row(
        "🔀 Branch",
        f"{pr_info.head_branch} → {pr_info.base_branch}"
    )
    table.add_row(
        "📊 Changes",
        f"[green]+{pr_info.total_additions}[/green] "
        f"[red]-{pr_info.total_deletions}[/red]"
    )
    table.add_row("📁 Files", str(len(pr_info.files)))

    console.print(Panel(table, title="PR Summary", border_style="blue"))


def print_files_table(pr_info):
    table = Table(
        title="Changed Files",
        show_header=True,
        header_style="bold magenta"
    )
    table.add_column("File", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Additions", justify="right", style="green")
    table.add_column("Deletions", justify="right", style="red")

    status_emoji = {
        "added": "🆕",
        "modified": "✏️",
        "removed": "🗑️",
        "renamed": "📝"
    }

    for f in pr_info.files:
        emoji = status_emoji.get(f.status, "❓")
        table.add_row(
            f.filename,
            f"{emoji} {f.status}",
            f"+{f.additions}",
            f"-{f.deletions}"
        )

    console.print(table)


@click.group()
def main():
    """🤖 PR Review Bot — AI-powered GitHub PR reviews using Groq + Llama 3"""
    pass

@main.command()
@click.option(
    "--repo", "-r",
    required=True,
    help="GitHub repo e.g. 'owner/repo' or full GitHub URL"
)
@click.option(
    "--pr", "-p",
    required=True,
    type=int,
    help="PR number e.g. 42"
)
@click.option(
    "--post/--no-post",
    default=False,
    help="Post review as GitHub comment (default: just print)"
)
@click.option(
    "--comment",
    is_flag=True,
    default=False,
    help="Post as issue comment instead of formal review (works on your own PRs)"
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Post even if bot has already reviewed this PR"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Show the full diff being sent to the LLM"
)
def review(repo, pr, post, comment, force, verbose):
    """Review a GitHub Pull Request with AI"""

    print_banner()

    # Validate config
    try:
        validate_config()
    except EnvironmentError as e:
        console.print(f"[red]{e}[/red]")
        raise click.Abort()

    # Parse repo
    client = GitHubClient()
    try:
        owner, repo_name = client.parse_repo(repo)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise click.Abort()

    # Fetch PR
    console.print(
        f"\n[cyan]📋 Fetching PR #{pr} from {owner}/{repo_name}...[/cyan]"
    )
    try:
        pr_info = client.get_pr_info(owner, repo_name, pr)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise click.Abort()

    # Print summary
    print_pr_summary(pr_info)
    print_files_table(pr_info)

    # Show diff if verbose
    if verbose:
        diff = client.format_diff_for_review(pr_info)
        console.print(Panel(diff, title="Full Diff", border_style="yellow"))

    # Check reviewable files
    reviewable_files = [f for f in pr_info.files if f.patch]
    skipped = len(pr_info.files) - len(reviewable_files)

    if skipped > 0:
        console.print(
            f"[yellow]⚠️  Skipping {skipped} binary file(s)[/yellow]"
        )

    if not reviewable_files:
        console.print("[red]❌ No reviewable files found[/red]")
        raise click.Abort()

    # Check for duplicate reviews before doing LLM call
    if post and not force:
        with console.status("[dim]Checking for existing reviews...[/dim]"):
            existing = client.get_existing_bot_comments(owner, repo_name, pr)
        if existing:
            console.print(
                f"[yellow]⚠️  Bot has already reviewed this PR "
                f"({len(existing)} time(s)).[/yellow]"
            )
            console.print(
                "[yellow]Use --force to post another review.[/yellow]"
            )
            # Still run the review locally, just don't post
            post = False

    # Token estimate warning
    reviewer = PRReviewer()
    stats = reviewer.get_usage_stats(pr_info)
    if stats["estimated_input_tokens"] > 6000:
        console.print(
            f"[yellow]⚠️  Large PR (~{stats['estimated_input_tokens']} tokens). "
            f"Diff will be truncated if needed.[/yellow]"
        )

    # Run LLM review
    console.print(
        f"\n[cyan]🔍 Analyzing {len(reviewable_files)} file(s) "
        f"with Llama 3 on Groq...[/cyan]"
    )

    review_text = None
    with console.status(
        "[bold green]Llama 3 is reading your code...[/bold green]",
        spinner="dots"
    ):
        try:
            review_text = reviewer.review_pr(pr_info)
        except Exception as e:
            console.print(f"[red]❌ LLM review failed: {e}[/red]")
            raise click.Abort()

    # Print review in terminal
    console.print("\n")
    console.print(Panel(
        Markdown(review_text),
        title="[bold green]✨ AI Code Review[/bold green]",
        border_style="green"
    ))

    # Post to GitHub
    if post:
        from pr_review_bot.formatter import format_github_comment
        github_comment = format_github_comment(review_text, pr_info, repo)

        console.print("\n[cyan]📤 Posting review to GitHub...[/cyan]")

        try:
            if comment:
                # Post as simple issue comment (works on your own PRs)
                result = client.post_issue_comment(
                    owner, repo_name, pr, github_comment
                )
                comment_url = result.get("html_url", "")
                console.print("[green]✅ Comment posted![/green]")
            else:
                # Post as formal PR review
                result = client.post_review(
                    owner, repo_name, pr, github_comment
                )
                comment_url = result.get("html_url", "")
                console.print("[green]✅ Review posted![/green]")

            console.print(
                f"[dim]🔗 View at: https://github.com/{owner}"
                f"/{repo_name}/pull/{pr}[/dim]"
            )

        except ValueError as e:
            # Self-review error — suggest --comment flag
            console.print(f"[red]{e}[/red]")
            console.print(
                "[yellow]💡 Try: review-bot review "
                f"--repo {repo} --pr {pr} --post --comment[/yellow]"
            )
        except Exception as e:
            console.print(f"[red]❌ Failed to post: {e}[/red]")
    else:
        console.print(
            "\n[dim]💡 Tip: Add --post to publish this as a GitHub comment[/dim]"
        )
        console.print(
            "[dim]💡 Tip: Add --post --comment to post on your own PRs[/dim]"
        )

@main.command()
def config():
    """Check your configuration and API keys"""
    console.print(Panel.fit(
        "[bold]Configuration Check[/bold]",
        border_style="cyan"
    ))

    from pr_review_bot.config import GITHUB_TOKEN, GROQ_API_KEY

    if GITHUB_TOKEN:
        masked = GITHUB_TOKEN[:8] + "..." + GITHUB_TOKEN[-4:]
        console.print(f"[green]✅ GITHUB_TOKEN:[/green] {masked}")
    else:
        console.print("[red]❌ GITHUB_TOKEN: Not set[/red]")

    if GROQ_API_KEY:
        masked = GROQ_API_KEY[:8] + "..." + GROQ_API_KEY[-4:]
        console.print(f"[green]✅ GROQ_API_KEY:[/green] {masked}")
    else:
        console.print("[red]❌ GROQ_API_KEY: Not set[/red]")

    if GITHUB_TOKEN:
        try:
            import requests
            resp = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {GITHUB_TOKEN}"}
            )
            if resp.status_code == 200:
                username = resp.json().get("login")
                console.print(
                    f"[green]✅ GitHub connection:[/green] "
                    f"Logged in as @{username}"
                )
            else:
                console.print(
                    "[red]❌ GitHub connection: Token invalid[/red]"
                )
        except Exception:
            console.print(
                "[red]❌ GitHub connection: Could not connect[/red]"
            )


if __name__ == "__main__":
    main()