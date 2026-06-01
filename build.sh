#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Build the frontend SPA
echo "Building the React frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Build complete."
