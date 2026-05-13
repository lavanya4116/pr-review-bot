from setuptools import setup, find_packages

setup(
    name="pr-review-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "requests",
        "groq",
        "python-dotenv",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "review-bot=pr_review_bot.cli:main",
        ],
    },
)