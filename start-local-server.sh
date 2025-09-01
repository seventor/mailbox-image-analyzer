#!/bin/bash

# Mailbox Image Analyzer - Local Development Server
# This script starts a local HTTP server for testing the webapp

echo "🚀 Starting Mailbox Image Analyzer Local Server..."
echo "📍 Server will run from: $(pwd)/webapp"
echo "🌐 Access your webapp at: http://localhost:8000/index.html"
echo ""

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8000 is already in use. Stopping existing processes..."
    lsof -ti:8000 | xargs kill -9
    sleep 1
fi

# Change to webapp directory and start server
cd webapp

echo "📁 Starting server from: $(pwd)"
echo "🔄 Server starting... Press Ctrl+C to stop"
echo ""

# Start Python HTTP server
python3 -m http.server 8000

echo ""
echo "👋 Server stopped. Goodbye!"
