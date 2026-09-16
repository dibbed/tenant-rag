#!/usr/bin/env python3
"""Setup configuration for RAG Telegram Assistant."""

import os

from setuptools import find_packages, setup


# Read README for long description
def read_readme():
    """Read README.md for long description."""
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return "RAG Telegram Assistant - A production-ready Telegram bot using Retrieval-Augmented Generation"

# Read requirements
def read_requirements(filename):
    """Read requirements from file."""
    req_path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(req_path):
        with open(req_path, "r", encoding="utf-8") as f:
            return [
                line.strip() 
                for line in f 
                if line.strip() and not line.startswith("#")
            ]
    return []

# Core requirements
install_requires = read_requirements("requirements.txt")

# Development requirements
dev_requires = [
    "pytest>=8.2.2",
    "pytest-asyncio>=0.23.7",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "hypothesis>=6.104.2",
    "factory-boy>=3.3.0",
    "mypy>=1.10.1",
    "ruff>=0.5.0",
    "pre-commit>=3.7.1",
    "bandit>=1.7.9",
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.5.27",
]

# Full feature requirements
full_requires = install_requires + [
    "chromadb>=0.5.0",
    "llama-index>=0.10.43",
    "spacy>=3.7.5",
    "anthropic>=0.28.1",
]

setup(
    name="ragbot",
    version="1.0.0",
    description="A production-ready Telegram bot using Retrieval-Augmented Generation (RAG)",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="RAG Bot Team",
    author_email="support@ragbot.dev",
    url="https://github.com/dibbed/rag-telegram-assistant",
    packages=find_packages(exclude=["tests*", "docs*"]),
    include_package_data=True,
    python_requires=">=3.10",
        install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
        "full": full_requires,
        "offline": [
            "transformers>=4.43.0",
        ],
        "test": [
            "pytest>=8.2.2",
            "pytest-asyncio>=0.23.7",
            "pytest-cov>=5.0.0",
            "pytest-mock>=3.14.0",
        ],
        "docs": [
            "mkdocs>=1.6.0",
            "mkdocs-material>=9.5.27",
        ],
    },
    entry_points={
        "console_scripts": [
            "ragbot=ragbot.main:main",
            "ragbot-setup=ragbot.configs.setup:main",
            "ragbot-migrate=ragbot.configs.migrate:main",
            "ragbot-cli=ragbot.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="telegram bot rag retrieval augmented generation ai chatbot nlp",
    project_urls={
        "Bug Reports": "https://github.com/dibbed/rag-telegram-assistant/issues",
        "Source": "https://github.com/dibbed/rag-telegram-assistant",
        "Documentation": "https://github.com/dibbed/rag-telegram-assistant/docs",
    },
    zip_safe=False,
)


