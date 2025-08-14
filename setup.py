"""Setup configuration for django-rest-framework-mcp."""

from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="django-rest-framework-mcp",
    version="0.1.0a2",
    author="Django REST Framework MCP Contributors",
    description="Expose Django REST Framework APIs as MCP servers for LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zacharypodbela/django-rest-framework-mcp",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Django",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Django>=4.0,<5.0",
        "djangorestframework>=3.14.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-django>=4.5.0",
            "pytest-cov>=4.0.0",
            "coverage>=6.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
            "django-stubs>=4.0.0",
            "djangorestframework-stubs>=3.14.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-django>=4.5.0",
            "pytest-cov>=4.0.0",
            "coverage>=6.0",
        ],
    },
)
