import click

@click.group()
def main():
    """🤖 PR Review Bot — AI-powered GitHub PR reviews using Groq + Llama 3"""
    pass

@main.command()
@click.option("--repo", "-r", required=True, help="GitHub repo e.g. username/reponame")
@click.option("--pr", "-p", required=True, type=int, help="PR number e.g. 42")
def review(repo, pr):
    """Review a GitHub Pull Request"""
    click.echo(f"🔍 Reviewing PR #{pr} in {repo}...")
    click.echo("(Not implemented yet — coming next step!)")

if __name__ == "__main__":
    main()