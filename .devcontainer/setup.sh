#!/bin/bash
set -e

echo "Setting up locale..."

# Install and configure locale (fixes "cannot change locale" warnings)
apt-get update && apt-get install -y locales
sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen
locale-gen en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

echo "Setting up Python environment..."

# Upgrade pip
pip install --upgrade pip

# Install package in editable mode with dev deps
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

echo "✓ Ready! Run: media-feed --help"
