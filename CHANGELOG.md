# Changelog

## Version 1.0.0 - Initial Release

### Features
- ✅ Voice cloning using IndexTTS-2 (Bilibili's model)
- ✅ Modern PyQt6 GUI with minimalistic design
- ✅ Microphone recording (5 seconds)
- ✅ Drag & drop file upload
- ✅ Click to select file upload
- ✅ Support for WAV, MP3, M4A, AIFF, FLAC formats
- ✅ Audio playback for voice samples
- ✅ Audio playback for generated speech
- ✅ Auto-play generated audio
- ✅ Loading animations and status updates
- ✅ Grey tile design for file displays
- ✅ Countdown timer for recording
- ✅ MPS (Metal Performance Shaders) support for Apple Silicon

### Technical Details
- **UI Framework**: PyQt6
- **Audio Recording**: sounddevice (better macOS permission handling)
- **Audio Processing**: soundfile, numpy, scipy
- **Model**: IndexTTS-2 from Bilibili
- **Platform**: macOS (Apple Silicon optimized)

### Known Issues
- Microphone permission must be granted to Terminal/Python
- First run may require permission reset: `tccutil reset Microphone`

### File Structure
```
bilibili-voice-clone-mac/
├── voice_clone_app.py      # Main UI application
├── voice_clone_model.py    # Model interface and audio utilities
├── requirements.txt        # Python dependencies
├── README.md              # Setup and usage instructions
├── CHANGELOG.md           # Version history
├── soundbites/            # Sample audio files for testing (included in repo)
│   ├── john_cena_ch.wav
│   ├── john_cena_eng.wav
│   └── README.md
├── recordings/            # Recorded audio files (gitignored)
├── output/               # Generated audio files (gitignored)
└── index-tts/            # IndexTTS-2 repository (gitignored)
```

### Code Statistics
- Main UI: 953 lines
- Model Interface: 244 lines
- Total: 1,197 lines of clean, well-documented Python code

