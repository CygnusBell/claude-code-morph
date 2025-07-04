#!/usr/bin/env python
"""Setup configuration for Claude Code Morph."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read minimal requirements (core dependencies only)
requirements = []
with open("requirements-minimal.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Optional dependencies for full features
extras_require = {
    'context': [
        'chromadb>=0.4.22',
        'sentence-transformers>=2.2.2',
        'watchdog>=4.0.0',
        'tiktoken>=0.5.2',
        'pypdf>=3.17.4',
    ],
    'ai': [
        'groq>=0.4.2',
        'openai>=1.12.0',
        'anthropic>=0.18.0',
    ],
    'all': [
        'chromadb>=0.4.22',
        'sentence-transformers>=2.2.2',
        'watchdog>=4.0.0',
        'tiktoken>=0.5.2',
        'pypdf>=3.17.4',
        'groq>=0.4.2',
        'openai>=1.12.0',
        'anthropic>=0.18.0',
    ]
}

setup(
    name="claude-code-morph",
    version="0.1.0",
    author="Claude Code Morph Contributors",
    author_email="contact@claude-code-morph.dev",
    description="A self-editable development environment powered by Claude CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kruger/claude-code-morph",
    project_urls={
        "Bug Tracker": "https://github.com/kruger/claude-code-morph/issues",
        "Documentation": "https://github.com/kruger/claude-code-morph#readme",
        "Source Code": "https://github.com/kruger/claude-code-morph",
    },
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    extras_require=extras_require,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    entry_points={
        "console_scripts": [
            "morph=claude_code_morph.cli:main",
            "claude-code-morph=claude_code_morph.cli:main",
        ],
    },
    keywords="claude cli development terminal tui textual",
    zip_safe=False,
)