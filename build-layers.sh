#!/bin/bash

# Build Lambda layers for local development
# This script creates the numpy and pillow layers needed for the Lambda functions

echo "Building Lambda layers..."

# Create numpy layer
echo "Building numpy layer..."
mkdir -p lambda/numpy-layer/python
pip install --platform manylinux2014_x86_64 --target=lambda/numpy-layer/python --implementation cp --python-version 3.11 --only-binary=:all: --upgrade numpy

# Create pillow layer
echo "Building pillow layer..."
mkdir -p lambda/pillow-layer/python
pip install --platform manylinux2014_x86_64 --target=lambda/pillow-layer/python --implementation cp --python-version 3.11 --only-binary=:all: --upgrade Pillow

echo "Lambda layers built successfully!"
echo "You can now run: cd cdk && npm run deploy:dev"
