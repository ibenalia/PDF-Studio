#!/bin/bash

# Installation Script for PDF Studio

echo "Installing PDF Studio with PoDoFo C++ engine..."

# Create data directories
echo "Creating data directories..."
mkdir -p data/uploads data/temp data/processed

# Build Docker image
echo "Building Docker image..."
docker build -t pdf-studio .

# Clean up old containers
echo "Cleaning up old containers..."
docker rm -f pdf-studio-container 2>/dev/null || true

# Start container
echo "Starting PDF Studio container..."
docker run -d --name pdf-studio-container -p 5000:5000 -v "$(pwd)/data:/app/data" pdf-studio

# Check if container is running
if [ "$(docker ps -q -f name=pdf-studio-container)" ]; then
    echo "PDF Studio is now running at http://localhost:5000"
else
    echo "Error starting container. Please check Docker logs."
    docker logs pdf-studio-container
fi 