#!/bin/bash

# ============================================
# Upstox Trading API - Quick Setup Script
# ============================================

echo "🚀 Setting up Upstox Trading API..."
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Create profile files if they don't exist
echo "📝 Creating environment profile files..."
python3 profile_manager.py create

# Set default profile to dev
echo "🔧 Setting default profile to '
