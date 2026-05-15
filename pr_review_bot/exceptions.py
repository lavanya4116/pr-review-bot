class PRReviewBotError(Exception):
    """Base exception for all PR Review Bot errors"""
    pass


class ConfigError(PRReviewBotError):
    """Missing or invalid configuration"""
    pass


class GitHubError(PRReviewBotError):
    """GitHub API related errors"""
    pass


class GitHubRateLimitError(GitHubError):
    """GitHub API rate limit exceeded"""
    pass


class GitHubNotFoundError(GitHubError):
    """PR or repo not found"""
    pass


class GitHubAuthError(GitHubError):
    """Invalid or expired GitHub token"""
    pass


class LLMError(PRReviewBotError):
    """Groq/LLM related errors"""
    pass


class LLMTimeoutError(LLMError):
    """LLM took too long to respond"""
    pass