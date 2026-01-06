#!/usr/bin/env python3.11
"""
Bilibili Voice Clone - Model Interface
Core functionality for using the IndexTTS-2 model for voice cloning.

This module provides a clean interface for:
- Finding and loading the IndexTTS-2 model
- Generating speech from text using a voice sample
- Audio processing utilities
"""

import os
import sys
import time
import tempfile
import subprocess
import warnings

# Fix protobuf compatibility issue
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Audio processing
try:
    import soundfile as sf
    import numpy as np
except ImportError:
    print("Error: soundfile and numpy required. Install with: pip install soundfile numpy")
    sys.exit(1)

# Add index-tts to path if it exists in parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
index_tts_dir = os.path.join(parent_dir, '20260102_MP3_To_Text_And_Text_To_Speech', 'index-tts')
if os.path.exists(index_tts_dir):
    sys.path.insert(0, index_tts_dir)

try:
    from indextts.infer_v2 import IndexTTS2
except ImportError:
    raise ImportError(
        "Could not import IndexTTS2. Please ensure index-tts is installed.\n\n"
        "Install with: pip install index-tts"
    )


def find_model_dir():
    """
    Find the IndexTTS-2 model directory.
    
    Returns:
        str: Path to model directory, or None if not found
    """
    # Try HuggingFace cache first
    hf_cache = os.path.expanduser("~/.cache/huggingface/IndexTeam/IndexTTS-2")
    if os.path.exists(hf_cache):
        config_path = os.path.join(hf_cache, "config.yaml")
        if os.path.exists(config_path):
            return hf_cache
    
    # Try local checkpoints directory in parent project
    parent_checkpoints = os.path.join(
        parent_dir, '20260102_MP3_To_Text_And_Text_To_Speech', 'index-tts', 'checkpoints'
    )
    if os.path.exists(parent_checkpoints):
        config_path = os.path.join(parent_checkpoints, "config.yaml")
        if os.path.exists(config_path):
            return parent_checkpoints
    
    return None


def load_model(model_dir=None):
    """
    Load the IndexTTS-2 model.
    
    Args:
        model_dir (str, optional): Path to model directory. If None, will try to find it automatically.
    
    Returns:
        IndexTTS2: Loaded model instance
    
    Raises:
        FileNotFoundError: If model directory is not found
        Exception: If model loading fails
    """
    if model_dir is None:
        model_dir = find_model_dir()
    
    if not model_dir:
        raise FileNotFoundError(
            "IndexTTS-2 model not found. Please download it first.\n\n"
            "Expected locations:\n"
            "  ~/.cache/huggingface/IndexTeam/IndexTTS-2\n"
            "  Or in the parent project's index-tts/checkpoints directory"
        )
    
    config_path = os.path.join(model_dir, "config.yaml")
    print(f"Loading IndexTTS-2 model from {model_dir}")
    
    tts = IndexTTS2(
        model_dir=model_dir,
        cfg_path=config_path,
        use_fp16=False,  # MPS doesn't support FP16
        use_cuda_kernel=False,
        use_deepspeed=False
    )
    
    return tts


def get_audio_duration(filepath):
    """
    Get audio file duration in seconds.
    
    Args:
        filepath (str): Path to audio file
    
    Returns:
        float: Duration in seconds
    
    Raises:
        Exception: If duration cannot be determined
    """
    try:
        data, sample_rate = sf.read(filepath)
        duration = len(data) / sample_rate
        return duration
    except Exception as e:
        # Try using ffprobe as fallback
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
                capture_output=True,
                text=True,
                check=True
            )
            return float(result.stdout.strip())
        except:
            raise Exception(f"Could not determine audio duration: {str(e)}")


def convert_to_wav(input_file):
    """
    Convert audio file to WAV format (24kHz mono).
    
    Args:
        input_file (str): Path to input audio file
    
    Returns:
        str: Path to converted WAV file
    
    Raises:
        Exception: If conversion fails
    """
    output_file = os.path.join(tempfile.gettempdir(), f"voice_sample_{int(time.time())}.wav")
    
    try:
        # Use ffmpeg to convert
        subprocess.run(
            ['ffmpeg', '-i', input_file, '-ar', '24000', '-ac', '1', output_file],
            check=True,
            capture_output=True
        )
        return output_file
    except subprocess.CalledProcessError as e:
        # Fallback: try using soundfile directly
        try:
            data, sr = sf.read(input_file)
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            # Resample to 24kHz if needed
            if sr != 24000:
                # Try scipy for better resampling, fallback to simple method
                try:
                    from scipy import signal
                    num_samples = int(len(data) * 24000 / sr)
                    data = signal.resample(data, num_samples)
                except ImportError:
                    # Simple resampling without scipy
                    num_samples = int(len(data) * 24000 / sr)
                    indices = np.linspace(0, len(data) - 1, num_samples)
                    data = np.interp(indices, np.arange(len(data)), data)
            sf.write(output_file, data, 24000)
            return output_file
        except Exception as e2:
            raise Exception(f"Failed to convert audio: {str(e2)}")


def validate_audio_file(filepath, max_duration=10.0):
    """
    Validate an audio file (check duration and convert if needed).
    
    Args:
        filepath (str): Path to audio file
        max_duration (float): Maximum allowed duration in seconds (default: 10.0)
    
    Returns:
        str: Path to validated/converted WAV file
    
    Raises:
        ValueError: If file is too long
        Exception: If validation or conversion fails
    """
    # Check duration
    duration = get_audio_duration(filepath)
    if duration > max_duration:
        raise ValueError(
            f"Audio file is too long ({duration:.1f} seconds). "
            f"Maximum allowed: {max_duration} seconds."
        )
    
    # Convert to WAV if needed
    if not filepath.lower().endswith('.wav'):
        filepath = convert_to_wav(filepath)
    
    return filepath


def generate_speech(model, voice_sample_path, text, output_path):
    """
    Generate speech from text using a voice sample.
    
    Args:
        model (IndexTTS2): Loaded IndexTTS-2 model
        voice_sample_path (str): Path to voice sample audio file (max 10 seconds)
        text (str): Text to speak
        output_path (str): Path where output audio will be saved
    
    Raises:
        Exception: If generation fails
    """
    model.infer(
        spk_audio_prompt=voice_sample_path,
        text=text,
        output_path=output_path,
        verbose=False
    )

