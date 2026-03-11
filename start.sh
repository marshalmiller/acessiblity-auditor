#!/bin/bash
# Quick start script for Accessibility Auditor

echo "🚀 Starting Accessibility Auditor..."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and set a secure SECRET_KEY for production!"
    echo ""
fi

# Start the application
echo "🏗️  Building and starting containers..."
docker-compose up -d --build

# Wait for the application to be ready
echo ""
echo "⏳ Waiting for application to start..."
sleep 5

# Check if the application is running
if curl -s http://localhost:5000 > /dev/null; then
    echo ""
    echo "✅ Accessibility Auditor is running!"
    echo ""
    echo "🌐 Access the application at: http://localhost:5000"
    echo ""
    echo "📊 View logs:    docker-compose logs -f"
    echo "🛑 Stop app:     docker-compose down"
    echo "🔄 Restart:      docker-compose restart"
    echo ""
else
    echo ""
    echo "⚠️  Application may still be starting. Check logs with:"
    echo "   docker-compose logs -f"
    echo ""
fi
