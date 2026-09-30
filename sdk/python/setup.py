"""
OffCall AI - Python Error Tracking SDK

Install:
    pip install offcall-errors

Usage:
    import offcall_errors
    offcall_errors.init(api_key="ofc_your_api_key")
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

# Read version from package
version = "1.0.0"

# Read README for long description
try:
    with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "OffCall AI Python Error Tracking SDK"

setup(
    name="offcall-errors",
    version=version,
    description="OffCall AI Python Error Tracking SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="OffCall AI",
    author_email="noreply@example.com",
    url="https://github.com/offcall-ai/offcall-python",
    project_urls={
        "Documentation": "https://github.com/cbrahmam/offcallai/blob/main/sdk/python/README.md",
        "Source": "https://github.com/offcall-ai/offcall-python",
        "Bug Tracker": "https://github.com/offcall-ai/offcall-python/issues",
    },
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.7",
    install_requires=[],  # No required dependencies - uses stdlib
    extras_require={
        "flask": ["flask>=1.0"],
        "django": ["django>=2.0"],
        "fastapi": ["fastapi>=0.50", "starlette>=0.12"],
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "isort>=5.0",
            "mypy>=0.900",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Bug Tracking",
        "Topic :: System :: Monitoring",
    ],
    keywords="error-tracking monitoring observability offcall",
    entry_points={
        "console_scripts": [
            "offcall-test=offcall_errors.cli:test_connection",
        ],
    },
)
