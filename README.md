# Bilibili Voice Clone - Mac App

A simple, user-friendly Mac application for voice cloning using Bilibili's IndexTTS-2 model. Clone any voice from a short audio sample (max 10 seconds) and generate speech in that voice.

## Features

- 🎤 **Voice Cloning**: Clone any voice from a 10-second audio sample
- 🎙️ **Microphone Recording**: Record 5 seconds directly from your Mac's microphone
- 📁 **Drag & Drop**: Easy file upload (supports WAV, MP3, M4A, AIFF, FLAC)
- ✍️ **Text-to-Speech**: Type any text and hear it in the cloned voice
- 🎵 **Audio Playback**: Instantly play generated speech
- ⚡ **Mac Optimized**: Uses MPS (Metal Performance Shaders) for fast inference on Apple Silicon

## Requirements

- macOS (Apple Silicon recommended for best performance)
- **Python 3.11** (required)
- ffmpeg (for audio conversion and recording)

## ⚠️ Important: Microphone Permission

**For the recording feature to work, you must grant microphone permission:**

1. Go to **System Settings → Privacy & Security → Microphone**
2. Enable permission for **Python** or **Terminal** (depending on how you run the app)
3. Restart the app after granting permission

**If you already granted permission but recording still doesn't work:**

Open Terminal and run:
```bash
tccutil reset Microphone
```

Then restart the app - it will prompt for permission again. This time click "OK" and it should work.

Without this permission, recordings will be silent.

## Installation

### Quick Setup (Recommended)

Run the setup script:

```bash
./setup.sh
```

This will:
- Check for Python 3 and ffmpeg
- Create a virtual environment
- Install all dependencies
- Check for the IndexTTS-2 model

### Manual Setup

#### 1. Install ffmpeg

```bash
brew install ffmpeg
```

#### 2. Set up Python Environment

**Important**: Python 3.11 is required.

```bash
# Check your Python version (should be 3.11)
python3.11 --version

# If you don't have Python 3.11, install it:
brew install python@3.11

# Create virtual environment with Python 3.11
python3.11 -m venv venv311
source venv311/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Install IndexTTS-2

Clone the IndexTTS repository and install it:

```bash
# Clone the repository
git clone https://github.com/index-tts/index-tts.git

# Navigate to the repository
cd index-tts

# Install in editable mode
pip install -e .

# Return to the project directory
cd ..
```

#### 4. Download IndexTTS-2 Model

**⚠️ Warning**: The model download is approximately **2.3 GB** and may take a while depending on your internet connection.

The model needs to be downloaded from HuggingFace:

```bash
# Install huggingface-hub CLI
pip install huggingface-hub

# Download the model (this will download ~2.3 GB)
hf download IndexTeam/IndexTTS-2 --local-dir ~/.cache/huggingface/IndexTeam/IndexTTS-2
```

## Usage

### Test Samples

The `soundbites/` folder contains sample audio files you can use to test the app:
- `john_cena_ch.wav` - John Cena speaking Chinese
- `john_cena_eng.wav` - John Cena speaking English

Drag and drop these files into the app to test voice cloning!

### Running the App

```bash
python3.11 voice_clone_app.py
```

### Using the App

1. **Load a Voice Sample**:
   - Click the drop zone area to browse and select an audio file (max 10 seconds)
   - Supported formats: WAV, MP3, M4A, AIFF, FLAC
   - Or click "🎤 Record 5 seconds" to record directly from your Mac's microphone

2. **Enter Text**:
   - Type the text you want to hear in the cloned voice
   - Supports Mandarin Chinese and other languages

3. **Generate & Play**:
   - Click "▶ Generate & Play"
   - Wait for the loading animation (speech generation takes a few seconds)
   - The audio will play automatically when ready

## Supported Audio Formats

The app accepts the following audio formats for voice samples:
- **WAV** (recommended)
- **MP3**
- **M4A**
- **AIFF**
- **FLAC**

All formats are automatically converted to WAV (24kHz mono) for processing.

## Limitations

- Voice samples must be **10 seconds or less** (this is a model limitation)
- First-time model loading takes a few minutes
- Speech generation takes 5-15 seconds depending on text length and your Mac's performance

## Troubleshooting

### Python Version Issues

If you get errors about Python version:
- **Python 3.11 is required**
- Check your version: `python3.11 --version`
- If you don't have Python 3.11, install it:
  ```bash
  brew install python@3.11
  # Then use: python3.11 -m venv venv311
  ```

### Model Not Found

If you see "Model directory not found", make sure:
1. The model is downloaded to `~/.cache/huggingface/IndexTeam/IndexTTS-2`

### ffmpeg Not Found

If recording fails, install ffmpeg:
```bash
brew install ffmpeg
```

### Import Errors

If you get import errors for IndexTTS2:
1. Make sure you've cloned the index-tts repository: `git clone https://github.com/index-tts/index-tts.git`
2. Make sure index-tts is installed: `cd index-tts && pip install -e .`

## Technical Details

- **Model**: IndexTTS-2 (Bilibili's voice cloning model)
- **Sample Rate**: 24kHz
- **Audio Format**: WAV (mono)
- **Device**: Automatically uses MPS on Apple Silicon, falls back to CPU

## License

This app uses IndexTTS-2, which has its own license. Please refer to the IndexTTS-2 repository for licensing information.

## Credits

- IndexTTS-2 by Bilibili/IndexTeam
- Built for Mac users who want a simple voice cloning interface

