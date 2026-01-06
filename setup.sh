#!/bin/bash
# Setup script for Bilibili Voice Clone Mac App

set -e

echo "🎤 Bilibili Voice Clone - Setup Script"
echo "========================================"
echo ""

# Check if Python 3.11 is available (required)
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✓ Python 3.11 found: $(python3.11 --version)"
else
    echo "❌ Error: Python 3.11 is required but not found."
    echo ""
    echo "To install Python 3.11 on Mac:"
    echo "  brew install python@3.11"
    echo ""
    echo "After installation, run this setup script again."
    exit 1
fi
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg not found. Installing with Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "❌ Error: Homebrew not found. Please install ffmpeg manually:"
        echo "   brew install ffmpeg"
        exit 1
    fi
else
    echo "✓ ffmpeg found: $(ffmpeg -version | head -n 1)"
fi
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with $PYTHON_CMD..."
    $PYTHON_CMD -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo ""

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo ""

# Check if index-tts needs to be installed
echo "Checking for index-tts..."
if python3 -c "import indextts" 2>/dev/null; then
    echo "✓ index-tts is installed"
else
    echo "⚠️  index-tts not found. You may need to install it:"
    echo "   pip install index-tts"
    echo "   Or install from source if you have the source code"
fi
echo ""

# Check for model
echo "Checking for IndexTTS-2 model..."
MODEL_PATH="$HOME/.cache/huggingface/IndexTeam/IndexTTS-2"
if [ -d "$MODEL_PATH" ] && [ -f "$MODEL_PATH/config.yaml" ]; then
    echo "✓ Model found at: $MODEL_PATH"
else
    echo "⚠️  Model not found. You need to download it:"
    echo "   pip install huggingface-hub"
    echo "   huggingface-cli download IndexTeam/IndexTTS-2 --local-dir $MODEL_PATH"
fi
echo ""

echo "========================================"
echo "✅ Setup complete!"
echo ""
echo "To run the app:"
echo "   source venv/bin/activate"
echo "   python voice_clone_app.py"
echo ""

