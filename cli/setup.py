"""
OffCall AI CLI

Install:
    pip install offcall-cli

Usage:
    offcall incidents list
    offcall alerts list --severity=critical
    offcall oncall who
    offcall deploy notify --service=api --version=1.2.3
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

version = "1.0.1"

try:
    with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "OffCall AI Command Line Interface"

setup(
    name="offcall-cli",
    version=version,
    description="OffCall AI Command Line Interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="OffCall AI",
    author_email="noreply@example.com",
    url="https://github.com/offcall-ai/offcall-cli",
    project_urls={
        "Documentation": "https://github.com/cbrahmam/offcallai/blob/main/cli/README.md",
        "Source": "https://github.com/offcall-ai/offcall-cli",
    },
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0",
        "rich>=12.0",
        "httpx>=0.23",
        "pyyaml>=6.0",
        "python-dateutil>=2.8",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Systems Administration",
    ],
    entry_points={
        "console_scripts": [
            "offcall=offcall.cli:main",
        ],
    },
)
