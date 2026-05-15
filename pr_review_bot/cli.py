import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.spinner import Spinner
from rich import print as rprint
from pr_review_bot.config import validate_config
from pr_review_bot.github_client import GitHubClient

console = Console()


def print_banner():
    """Print the tool banner"""
    console.print(Panel.fit(
        "[bold cyan]🤖 PR Review Bot[/bold cyan]\n"
        "[dim]AI-powered code reviews using Groq + Llama 3[/dim]",
        border_style="cyan"
    ))


def print_pr_summary(pr_info):
    """Print a nice summary table of the PR"""
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
    """Print a table of changed files"""
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
    help="Post review as a GitHub comment (default: just print)"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Show the full diff being sent to the LLM"
)
def review(repo, pr, post, verbose):
    """Review a GitHub Pull Request with AI"""

    print_banner()

    # Step 1: Validate config (fail fast if keys missing)
    try:
        validate_config()
    except EnvironmentError as e:
        console.print(f"[red]{e}[/red]")
        raise click.Abort()

    # Step 2: Parse repo string
    client = GitHubClient()
    try:
        owner, repo_name = client.parse_repo(repo)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise click.Abort()

    # Step 3: Fetch PR info
    console.print(
        f"\n[cyan]📋 Fetching PR #{pr} from {owner}/{repo_name}...[/cyan]"
    )
    try:
        pr_info = client.get_pr_info(owner, repo_name, pr)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise click.Abort()

    # Step 4: Print PR summary
    print_pr_summary(pr_info)
    print_files_table(pr_info)

    # Step 5: Show diff if verbose
    if verbose:
        diff = client.format_diff_for_review(pr_info)
        console.print(Panel(diff, title="Full Diff", border_style="yellow"))

    # Step 6: Skip files with no diff (binary files)
    reviewable_files = [f for f in pr_info.files if f.patch]
    skipped = len(pr_info.files) - len(reviewable_files)

    if skipped > 0:
        console.print(
            f"[yellow]⚠️  Skipping {skipped} binary file(s) "
            f"(no diff available)[/yellow]"
        )

    if not reviewable_files:
        console.print(
            "[red]❌ No reviewable files found "
            "(all files are binary)[/red]"
        )
        raise click.Abort()

    # Step 7: Run LLM review (placeholder for now — next step)
    console.print(
        f"\n[cyan]🔍 Analyzing {len(reviewable_files)} file(s) "
        f"with Llama 3...[/cyan]"
    )
    console.print(
        "[yellow]⏳ LLM integration coming next step![/yellow]"
    )


@main.command()
def config():
    """Check your configuration and API keys"""
    console.print(Panel.fit(
        "[bold]Configuration Check[/bold]",
        border_style="cyan"
    ))

    from pr_review_bot.config import GITHUB_TOKEN, GROQ_API_KEY

    # Check GitHub token
    if GITHUB_TOKEN:
        masked = GITHUB_TOKEN[:8] + "..." + GITHUB_TOKEN[-4:]
        console.print(f"[green]✅ GITHUB_TOKEN:[/green] {masked}")
    else:
        console.print("[red]❌ GITHUB_TOKEN: Not set[/red]")

    # Check Groq key
    if GROQ_API_KEY:
        masked = GROQ_API_KEY[:8] + "..." + GROQ_API_KEY[-4:]
        console.print(f"[green]✅ GROQ_API_KEY:[/green] {masked}")
    else:
        console.print("[red]❌ GROQ_API_KEY: Not set[/red]")

    # Test GitHub connection
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