#!/bin/bash
set -e

echo "Setting up Python environment..."

# Upgrade pip
pip install --upgrade pip

# Install package in editable mode with dev deps
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

echo "✓ Ready! Run: media-feed --help"
