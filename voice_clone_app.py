#!/usr/bin/env python3.11
"""
Bilibili Voice Clone - Mac App UI
A simple GUI for voice cloning using IndexTTS-2 (Bilibili's voice cloning model)

This file contains only the UI code. The model functionality is in voice_clone_model.py
"""

import os
import sys
import time
import threading
import tempfile
import subprocess
import math
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QFrame, QDialog,
    QGroupBox, QCheckBox, QLineEdit, QSpinBox, QDoubleSpinBox, QScrollArea,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QDragEnterEvent, QDropEvent

# Import model functionality
from voice_clone_model import (
    find_model_dir,
    load_model,
    get_audio_duration,
    convert_to_wav,
    validate_audio_file,
    generate_speech
)


class LoadingSpinner(QWidget):
    """Custom loading spinner widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.setFixedSize(60, 60)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = 20
        
        pen = QPen(QColor("#007AFF"), 4)
        painter.setPen(pen)
        
        # Draw rotating arc
        start_angle = self.angle * 16  # Qt uses 1/16th degree units
        span_angle = 270 * 16  # 3/4 circle
        
        painter.drawArc(
            center_x - radius, center_y - radius,
            radius * 2, radius * 2,
            start_angle, span_angle
        )
    
    def start_animation(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(30)
    
    def update_angle(self):
        self.angle = (self.angle + 10) % 360
        self.update()
    
    def stop_animation(self):
        if hasattr(self, 'timer'):
            self.timer.stop()


class CountdownDialog(QDialog):
    """Countdown dialog for recording"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recording")
        self.setFixedSize(320, 280)
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.countdown_label = QLabel("", self)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 48px; color: #1a1a1a;")
        layout.addWidget(self.countdown_label)
        
        self.recording_label = QLabel("", self)
        self.recording_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recording_label.setStyleSheet("font-size: 12px; color: #666666; margin-top: 10px;")
        layout.addWidget(self.recording_label)
        
        self.setLayout(layout)
        
        # Center window
        if parent:
            parent_geometry = parent.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)


class VoiceCloneApp(QMainWindow):
    # Signals for thread-safe GUI updates
    model_loaded_signal = pyqtSignal()
    model_error_signal = pyqtSignal(str)
    status_update_signal = pyqtSignal(str)
    button_enable_signal = pyqtSignal(object, bool)
    load_sample_signal = pyqtSignal(str, str)
    show_message_signal = pyqtSignal(str, str)  # title, message
    update_countdown_signal = pyqtSignal(int)  # remaining seconds
    close_countdown_signal = pyqtSignal()
    recording_complete_signal = pyqtSignal(str, str)  # filepath, display_name
    generation_complete_signal = pyqtSignal(str)  # output_path
    generation_error_signal = pyqtSignal(str)  # error_message
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bilibili Voice Clone - Mac")
        self.setMinimumSize(600, 800)
        self.resize(600, 900)
        
        # Variables
        self.tts = None
        self.voice_sample_path = None
        self.generated_audio_path = None
        self.is_generating = False
        self.audio_process = None
        self.countdown_window = None
        self.model_loaded = False
        self.loading_active = False
        self.loading_dots = 0
        self.advanced_mode = False  # Start in easy mode
        
        # Connect signals
        self.model_loaded_signal.connect(self.on_model_loaded)
        self.model_error_signal.connect(self.on_model_error)
        self.status_update_signal.connect(self.on_status_update)
        self.button_enable_signal.connect(self.on_button_enable)
        self.load_sample_signal.connect(self.on_load_sample)
        self.show_message_signal.connect(self.on_show_message)
        self.update_countdown_signal.connect(self.on_update_countdown)
        self.close_countdown_signal.connect(self.on_close_countdown)
        self.recording_complete_signal.connect(self.on_recording_complete)
        self.generation_complete_signal.connect(self.on_generation_complete)
        self.generation_error_signal.connect(self.on_generation_error)
        
        # Create loading screen first
        self.create_loading_screen()
        
        # Initialize model in background
        self.init_model_thread = threading.Thread(target=self.init_model, daemon=True)
        self.init_model_thread.start()
    
    def init_model(self):
        """Initialize the IndexTTS-2 model"""
        try:
            # Use model interface to load
            self.tts = load_model()
            
            # Emit signal to update GUI from main thread
            self.model_loaded_signal.emit()
            
        except FileNotFoundError as e:
            self.model_loaded = True
            self.model_loaded_signal.emit()
            QTimer.singleShot(100, lambda: self.show_message_signal.emit("Model Not Found", str(e)))
            QTimer.singleShot(100, lambda: self.status_update_signal.emit("ERROR: Model not found"))
        except Exception as e:
            error_msg = f"Failed to load model: {str(e)}"
            self.model_loaded = True
            self.model_loaded_signal.emit()
            QTimer.singleShot(100, lambda: self.show_message_signal.emit("Model Loading Error", error_msg))
            QTimer.singleShot(100, lambda: self.status_update_signal.emit(f"ERROR: {error_msg}"))
            print(f"Error: {e}")
    
    def on_model_loaded(self):
        """Handle model loaded signal"""
        self.model_loaded = True
        self.show_main_content()
        QTimer.singleShot(100, lambda: self.status_update_signal.emit("Model loaded! Drop an audio file or record from microphone."))
        QTimer.singleShot(100, lambda: self.button_enable_signal.emit(self.play_button, True))
        QTimer.singleShot(100, lambda: self.button_enable_signal.emit(self.record_button, True))
    
    def on_model_error(self, error_msg):
        """Handle model error signal"""
        QMessageBox.critical(self, "Model Loading Error", error_msg)
        self.status_update_signal.emit(f"ERROR: {error_msg}")
    
    def on_status_update(self, text):
        """Handle status update signal"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(text)
    
    def on_button_enable(self, button, enabled):
        """Handle button enable signal"""
        button.setEnabled(enabled)
    
    def on_load_sample(self, filepath, display_name):
        """Handle load sample signal"""
        self.load_voice_sample(filepath, display_name)
    
    def on_show_message(self, title, message):
        """Handle show message signal"""
        QMessageBox.critical(self, title, message)
    
    def on_update_countdown(self, remaining):
        """Handle countdown update signal"""
        if self.countdown_window:
            if remaining > 0:
                self.countdown_window.countdown_label.setText(str(remaining))
                self.countdown_window.countdown_label.setStyleSheet("font-size: 48px; color: #007AFF;")
                self.countdown_window.recording_label.setText(f"Recording... {remaining} seconds")
                self.countdown_window.recording_label.setStyleSheet("font-size: 12px; color: #007AFF;")
            else:
                # Recording done
                self.countdown_window.countdown_label.setText("Done!")
                self.countdown_window.countdown_label.setStyleSheet("font-size: 24px; color: #27ae60;")
                self.countdown_window.recording_label.setText("Recording complete")
                self.countdown_window.recording_label.setStyleSheet("font-size: 12px; color: #27ae60;")
    
    def on_close_countdown(self):
        """Handle close countdown signal"""
        if self.countdown_window:
            self.countdown_window.close()
            self.countdown_window = None
    
    def on_recording_complete(self, filepath, display_name):
        """Handle recording complete signal"""
        # Close window after a brief delay
        QTimer.singleShot(500, lambda: self.close_countdown_signal.emit())
        QTimer.singleShot(600, lambda: self.load_sample_signal.emit(filepath, display_name))
        QTimer.singleShot(600, lambda: self.status_update_signal.emit("Recording complete! Enter text and click Generate & Play."))
        QTimer.singleShot(600, lambda: self.button_enable_signal.emit(self.record_button, True))
    
    def on_generation_complete(self, output_path):
        """Handle generation complete signal"""
        
        self.animate_loading(False)
        # Store generated audio path
        self.generated_audio_path = output_path
        
        # Update generated audio display
        self.generated_audio_label.setText(f"{os.path.basename(output_path)}")
        self.generated_audio_frame.show()
        self.play_generated_btn.setEnabled(True)
        
        self.status_update_signal.emit("Speech generated! Auto-playing...")
        
        # Auto-play audio using non-blocking playback
        try:
            process = subprocess.Popen(
                ["afplay", output_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            print(f"Auto-play started with PID: {process.pid}")
            QTimer.singleShot(1000, lambda: self.status_update_signal.emit("Playback started!"))
        except Exception as e:
            self.status_update_signal.emit("ERROR: Failed to play audio.")
        
        # Re-enable buttons
        self.is_generating = False
        self.play_button.setEnabled(True)
        self.record_button.setEnabled(True)
    
    def on_generation_error(self, error_msg):
        """Handle generation error signal"""
        self.animate_loading(False)
        self.status_update_signal.emit(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Generation Error", error_msg)
        self.is_generating = False
        self.play_button.setEnabled(True)
        self.record_button.setEnabled(True)
    
    def create_loading_screen(self):
        """Create loading screen with spinner"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        central_widget.setStyleSheet("background-color: white;")
        
        # Spinner
        self.spinner = LoadingSpinner()
        self.spinner.start_animation()
        layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Loading text (below spinner)
        loading_text = QLabel("Model setting up...")
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text.setStyleSheet("font-size: 14px; color: #666666; margin-top: 20px;")
        layout.addWidget(loading_text)
        
        central_widget.setLayout(layout)
    
    def show_main_content(self):
        """Show main content after model is loaded"""
        self.model_loaded = True
        if hasattr(self, 'spinner'):
            self.spinner.stop_animation()
        self.create_widgets()
    
    def create_widgets(self):
        """Create the GUI widgets"""
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background-color: white;")
        self.setCentralWidget(scroll_area)
        
        # Create content widget
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: white;")
        scroll_area.setWidget(content_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(0)
        
        # Header with title and mode toggle
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Voice Clone")
        title_label.setStyleSheet("font-size: 28px; color: #1a1a1a; font-weight: normal;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Mode toggle button
        self.mode_toggle_btn = QPushButton("Advanced")
        self.mode_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #666666;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                color: #1a1a1a;
            }
            QPushButton:pressed {
                background-color: #e8e8e8;
            }
        """)
        self.mode_toggle_btn.clicked.connect(self.toggle_mode)
        self.mode_toggle_btn.setFixedHeight(32)
        header_layout.addWidget(self.mode_toggle_btn)
        
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(25)
        
        # Voice sample section
        voice_layout = QVBoxLayout()
        voice_layout.setSpacing(8)
        
        section_label = QLabel("Voice Sample")
        section_label.setStyleSheet("font-size: 11px; color: #666666;")
        voice_layout.addWidget(section_label)
        
        # Drop zone - clickable frame
        class ClickableFrame(QFrame):
            def __init__(self, parent, callback):
                super().__init__(parent)
                self.parent_app = parent
                self.callback = callback
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setAcceptDrops(True)
                self.drag_active = False
            
            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.callback()
            
            def dragEnterEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    self.drag_active = True
                    self.setStyleSheet("""
                        QFrame {
                            background-color: #f5f5f5;
                            border: 2px dashed #007AFF;
                            border-radius: 4px;
                        }
                    """)
            
            def dragMoveEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
            
            def dragLeaveEvent(self, event):
                self.drag_active = False
                self.setStyleSheet("""
                    QFrame {
                        background-color: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 4px;
                    }
                """)
            
            def dropEvent(self, event):
                if event.mimeData().hasUrls():
                    filepath = event.mimeData().urls()[0].toLocalFile()
                    if filepath:
                        self.parent_app.load_voice_sample(filepath)
                    event.acceptProposedAction()
                self.drag_active = False
                self.setStyleSheet("""
                    QFrame {
                        background-color: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 4px;
                    }
                """)
        
        class ClickableLabel(QLabel):
            def __init__(self, text, callback):
                super().__init__(text)
                self.callback = callback
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            
            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.callback()
        
        self.drop_zone = ClickableFrame(self, self.browse_audio_file)
        self.drop_zone.setFixedHeight(100)
        self.drop_zone.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        
        drop_layout = QVBoxLayout()
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.drop_label = ClickableLabel("Click to select file or drag file here\nWAV, MP3, M4A, AIFF, FLAC • Max 10 seconds", self.browse_audio_file)
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("font-size: 11px; color: #999999; border: none;")
        drop_layout.addWidget(self.drop_label)
        
        # File info (hidden initially) - grey tile style
        self.file_info_frame = QFrame()
        self.file_info_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: none;
                border-radius: 4px;
            }
        """)
        file_info_layout = QHBoxLayout()
        file_info_layout.setContentsMargins(12, 10, 12, 10)
        
        self.file_name_label = QLabel("")
        self.file_name_label.setStyleSheet("font-size: 11px; color: #1a1a1a; background: transparent; border: none;")
        file_info_layout.addWidget(self.file_name_label)
        
        file_info_layout.addStretch()
        
        # Play button
        self.play_file_btn = QPushButton("▶")
        self.play_file_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #1a1a1a;
                border: 1px solid #999999;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        self.play_file_btn.setFixedSize(40, 32)
        self.play_file_btn.clicked.connect(self.play_voice_sample)
        file_info_layout.addWidget(self.play_file_btn)
        
        # Remove button
        self.remove_file_btn = QPushButton("×")
        self.remove_file_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #999999;
                border: none;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #fee;
                color: #c00;
                border-radius: 4px;
            }
        """)
        self.remove_file_btn.setFixedSize(32, 32)
        self.remove_file_btn.clicked.connect(self.remove_file)
        file_info_layout.addWidget(self.remove_file_btn)
        
        self.file_info_frame.setLayout(file_info_layout)
        self.file_info_frame.hide()
        
        drop_layout.addWidget(self.file_info_frame)
        self.drop_zone.setLayout(drop_layout)
        
        voice_layout.addWidget(self.drop_zone)
        voice_layout.addSpacing(12)
        
        # Record button
        self.record_button = QPushButton("Record")
        self.record_button.setStyleSheet(self.get_button_style())
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.record_audio)
        voice_layout.addWidget(self.record_button)
        
        main_layout.addLayout(voice_layout)
        main_layout.addSpacing(20)
        
        # Text input section
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        text_label = QLabel("Text to Speak")
        text_label.setStyleSheet("font-size: 11px; color: #666666;")
        text_layout.addWidget(text_label)
        
        self.text_input = QTextEdit()
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 12px;
                font-size: 13px;
                color: #1a1a1a;
            }
            QTextEdit:focus {
                border: 1px solid #999999;
            }
        """)
        self.text_input.setFixedHeight(120)  # Will be adjusted by mode
        text_layout.addWidget(self.text_input)
        
        main_layout.addLayout(text_layout)
        main_layout.addSpacing(15)
        
        # Advanced settings section (hidden in easy mode)
        self.advanced_section = QWidget()
        advanced_layout = QVBoxLayout()
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(8)
        
        # Emotion Vector Section
        emo_vec_label = QLabel("emotion vector")
        emo_vec_label.setStyleSheet("font-size: 9px; color: #999999; margin-bottom: 2px;")
        advanced_layout.addWidget(emo_vec_label)
        
        # Create 8 spin boxes for emotion vector (all in one row)
        self.emo_vec_spinboxes = []
        emo_labels = ["Happy", "Angry", "Sad", "Scared", "Disgusted", "Depressed", "Surprised", "Calm"]
        
        emo_row_layout = QHBoxLayout()
        emo_row_layout.setSpacing(6)
        
        for i in range(8):
            col_layout = QVBoxLayout()
            col_layout.setSpacing(2)
            
            label_widget = QLabel(emo_labels[i])
            label_widget.setStyleSheet("font-size: 9px; color: #666666;")
            label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_layout.addWidget(label_widget)
            
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0.0, 1.0)
            spinbox.setSingleStep(0.1)
            spinbox.setValue(0.0)
            spinbox.setDecimals(1)
            spinbox.setFixedWidth(60)
            spinbox.setFixedHeight(28)
            spinbox.setStyleSheet("""
                QDoubleSpinBox {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 3px;
                    padding: 2px;
                    font-size: 10px;
                }
                QDoubleSpinBox:focus {
                    border: 1px solid #999999;
                }
            """)
            spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.emo_vec_spinboxes.append(spinbox)
            col_layout.addWidget(spinbox)
            
            emo_row_layout.addLayout(col_layout)
        
        emo_row_layout.addStretch()
        advanced_layout.addLayout(emo_row_layout)
        
        advanced_layout.addSpacing(8)
        
        # Emotion Text Section
        emo_text_label = QLabel("Emotion Text (Optional)")
        emo_text_label.setStyleSheet("font-size: 11px; color: #666666;")
        advanced_layout.addWidget(emo_text_label)
        
        self.use_emo_text_checkbox = QCheckBox("Use emotion text instead of vector")
        self.use_emo_text_checkbox.setStyleSheet("font-size: 10px; color: #666666;")
        self.use_emo_text_checkbox.stateChanged.connect(self.on_emotion_text_toggled)
        advanced_layout.addWidget(self.use_emo_text_checkbox)
        
        self.emo_text_input = QLineEdit()
        self.emo_text_input.setPlaceholderText('e.g., "Speaking slowly and clearly"')
        self.emo_text_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 6px;
                font-size: 10px;
            }
            QLineEdit:focus {
                border: 1px solid #999999;
            }
        """)
        advanced_layout.addWidget(self.emo_text_input)
        advanced_layout.addSpacing(8)
        
        # Generation Controls
        gen_controls_label = QLabel("generation controls")
        gen_controls_label.setStyleSheet("font-size: 9px; color: #999999; margin-bottom: 2px;")
        advanced_layout.addWidget(gen_controls_label)
        
        self.use_fixed_length_checkbox = QCheckBox("Use fixed length")
        self.use_fixed_length_checkbox.setStyleSheet("font-size: 10px; color: #666666;")
        self.use_fixed_length_checkbox.setChecked(False)
        self.use_fixed_length_checkbox.stateChanged.connect(self.on_fixed_length_toggled)
        advanced_layout.addWidget(self.use_fixed_length_checkbox)
        
        gen_row = QHBoxLayout()
        gen_row.setSpacing(15)
        
        # Max Mel Tokens
        max_mel_col = QVBoxLayout()
        max_mel_col.setSpacing(2)
        max_mel_label = QLabel("Max Mel Tokens")
        max_mel_label.setStyleSheet("font-size: 9px; color: #666666;")
        max_mel_col.addWidget(max_mel_label)
        
        self.max_mel_tokens_spinbox = QSpinBox()
        self.max_mel_tokens_spinbox.setRange(50, 5000)
        self.max_mel_tokens_spinbox.setValue(1500)
        self.max_mel_tokens_spinbox.setSingleStep(50)
        self.max_mel_tokens_spinbox.setFixedWidth(100)
        self.max_mel_tokens_spinbox.setFixedHeight(28)
        self.max_mel_tokens_spinbox.setEnabled(False)  # Disabled by default
        self.max_mel_tokens_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 4px;
                font-size: 10px;
                color: #999999;
            }
        """)
        max_mel_col.addWidget(self.max_mel_tokens_spinbox)
        gen_row.addLayout(max_mel_col)
        
        # Length Penalty
        length_penalty_col = QVBoxLayout()
        length_penalty_col.setSpacing(2)
        length_penalty_label = QLabel("Length Penalty")
        length_penalty_label.setStyleSheet("font-size: 9px; color: #666666;")
        length_penalty_col.addWidget(length_penalty_label)
        
        self.length_penalty_spinbox = QDoubleSpinBox()
        self.length_penalty_spinbox.setRange(-2.0, 2.0)
        self.length_penalty_spinbox.setValue(0.0)
        self.length_penalty_spinbox.setSingleStep(0.1)
        self.length_penalty_spinbox.setDecimals(1)
        self.length_penalty_spinbox.setFixedWidth(80)
        self.length_penalty_spinbox.setFixedHeight(28)
        self.length_penalty_spinbox.setEnabled(False)  # Disabled by default
        self.length_penalty_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 4px;
                font-size: 10px;
                color: #999999;
            }
        """)
        self.length_penalty_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        length_penalty_col.addWidget(self.length_penalty_spinbox)
        gen_row.addLayout(length_penalty_col)
        
        gen_row.addStretch()
        advanced_layout.addLayout(gen_row)
        
        self.advanced_section.setLayout(advanced_layout)
        self.advanced_section.hide()  # Hidden in easy mode by default
        main_layout.addWidget(self.advanced_section)
        main_layout.addSpacing(15)
        
        # Generate button
        self.play_button = QPushButton("Generate")
        self.play_button.setStyleSheet(self.get_button_style())
        self.play_button.setEnabled(False)
        self.play_button.setFixedHeight(40)
        self.play_button.clicked.connect(self.generate_and_play)
        main_layout.addWidget(self.play_button)
        main_layout.addSpacing(8)
        
        # Loading label (below button)
        self.loading_label = QLabel("")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 11px; color: #999999;")
        main_layout.addWidget(self.loading_label)
        main_layout.addSpacing(12)
        
        # Generated audio section (hidden initially) - grey tile style
        self.generated_audio_frame = QFrame()
        self.generated_audio_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: none;
                border-radius: 4px;
            }
        """)
        generated_audio_inner_layout = QHBoxLayout()
        generated_audio_inner_layout.setContentsMargins(12, 10, 12, 10)
        
        self.generated_audio_label = QLabel("")
        self.generated_audio_label.setStyleSheet("font-size: 11px; color: #1a1a1a; background: transparent; border: none;")
        generated_audio_inner_layout.addWidget(self.generated_audio_label)
        
        generated_audio_inner_layout.addStretch()
        
        # Play generated audio button
        self.play_generated_btn = QPushButton("▶")
        self.play_generated_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #1a1a1a;
                border: 1px solid #999999;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        self.play_generated_btn.setFixedSize(40, 32)
        self.play_generated_btn.clicked.connect(self.play_generated_audio)
        generated_audio_inner_layout.addWidget(self.play_generated_btn)
        
        self.generated_audio_frame.setLayout(generated_audio_inner_layout)
        self.generated_audio_frame.hide()
        
        main_layout.addWidget(self.generated_audio_frame)
        main_layout.addSpacing(12)
        
        # Status bar
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("font-size: 10px; color: #999999;")
        main_layout.addWidget(self.status_label)
        
        main_layout.addStretch()
        
        content_widget.setLayout(main_layout)
    
    def get_button_style(self):
        """Get modern button style"""
        return """
            QPushButton {
                background-color: white;
                color: #1a1a1a;
                border: 1px solid #999999;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border: 1px solid #666666;
            }
            QPushButton:pressed {
                background-color: #e8e8e8;
            }
            QPushButton:disabled {
                background-color: white;
                color: #cccccc;
                border: 1px solid #cccccc;
            }
        """
    
    def set_button_enabled(self, button, enabled):
        """Set button enabled state"""
        button.setEnabled(enabled)
    
    def play_voice_sample(self):
        """Play the current voice sample"""
        
        if self.voice_sample_path and os.path.exists(self.voice_sample_path):
            file_size = os.path.getsize(self.voice_sample_path)
            
            try:
                # Use afplay with explicit audio device to avoid permission issues
                # Run in background and don't wait for completion
                process = subprocess.Popen(
                    ["afplay", self.voice_sample_path],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                self.status_label.setText(f"Playing: {os.path.basename(self.voice_sample_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to play audio:\n{str(e)}")
        else:
            if self.voice_sample_path:
                print(f"  Path was: {self.voice_sample_path}")
            QMessageBox.warning(self, "No File", "No voice sample loaded to play.")
    
    def play_generated_audio(self):
        """Play the generated audio"""
        if hasattr(self, 'generated_audio_path') and self.generated_audio_path and os.path.exists(self.generated_audio_path):
            try:
                # Use non-blocking playback with detached process
                process = subprocess.Popen(
                    ["afplay", self.generated_audio_path],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                self.status_label.setText(f"Playing: {os.path.basename(self.generated_audio_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to play audio:\n{str(e)}")
        else:
            print(f"No generated audio or file doesn't exist. Path: {getattr(self, 'generated_audio_path', 'None')}")
            QMessageBox.warning(self, "No Audio", "No generated audio available to play.")
    
    def remove_file(self):
        """Remove the current file from drop zone"""
        self.voice_sample_path = None
        self.file_info_frame.hide()
        self.drop_label.show()
        self.status_label.setText("File removed")
    
    def toggle_mode(self):
        """Toggle between Easy and Advanced mode"""
        self.advanced_mode = not self.advanced_mode
        
        if self.advanced_mode:
            # Switch to Advanced mode
            self.mode_toggle_btn.setText("Easy")
            if hasattr(self, 'advanced_section'):
                self.advanced_section.show()
            # Make text box smaller in advanced mode
            if hasattr(self, 'text_input'):
                self.text_input.setFixedHeight(80)
        else:
            # Switch to Easy mode
            self.mode_toggle_btn.setText("Advanced")
            if hasattr(self, 'advanced_section'):
                self.advanced_section.hide()
            # Restore text box height in easy mode
            if hasattr(self, 'text_input'):
                self.text_input.setFixedHeight(120)
    
    def on_emotion_text_toggled(self, state):
        """Handle emotion text checkbox toggle - disable/enable emotion vector controls"""
        if hasattr(self, 'emo_vec_spinboxes'):
            # If checkbox is checked (using emotion text), disable emotion vector spinboxes
            enabled = (state == 0)  # 0 = unchecked, 2 = checked
            for spinbox in self.emo_vec_spinboxes:
                spinbox.setEnabled(enabled)
                # Update styling to show disabled state
                if enabled:
                    spinbox.setStyleSheet("""
                        QDoubleSpinBox {
                            background-color: white;
                            border: 1px solid #e0e0e0;
                            border-radius: 3px;
                            padding: 2px;
                            font-size: 10px;
                        }
                        QDoubleSpinBox:focus {
                            border: 1px solid #999999;
                        }
                    """)
                else:
                    spinbox.setStyleSheet("""
                        QDoubleSpinBox {
                            background-color: #f5f5f5;
                            border: 1px solid #e0e0e0;
                            border-radius: 3px;
                            padding: 2px;
                            font-size: 10px;
                            color: #999999;
                        }
                    """)
    
    def on_fixed_length_toggled(self, state):
        """Handle fixed length checkbox toggle - disable/enable generation controls"""
        enabled = (state == 2)  # 2 = checked, 0 = unchecked
        
        if hasattr(self, 'max_mel_tokens_spinbox'):
            self.max_mel_tokens_spinbox.setEnabled(enabled)
            if enabled:
                self.max_mel_tokens_spinbox.setStyleSheet("""
                    QSpinBox {
                        background-color: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 3px;
                        padding: 4px;
                        font-size: 10px;
                    }
                    QSpinBox:focus {
                        border: 1px solid #999999;
                    }
                """)
            else:
                self.max_mel_tokens_spinbox.setStyleSheet("""
                    QSpinBox {
                        background-color: #f5f5f5;
                        border: 1px solid #e0e0e0;
                        border-radius: 3px;
                        padding: 4px;
                        font-size: 10px;
                        color: #999999;
                    }
                """)
        
        if hasattr(self, 'length_penalty_spinbox'):
            self.length_penalty_spinbox.setEnabled(enabled)
            if enabled:
                self.length_penalty_spinbox.setStyleSheet("""
                    QDoubleSpinBox {
                        background-color: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 3px;
                        padding: 4px;
                        font-size: 10px;
                    }
                    QDoubleSpinBox:focus {
                        border: 1px solid #999999;
                    }
                """)
            else:
                self.length_penalty_spinbox.setStyleSheet("""
                    QDoubleSpinBox {
                        background-color: #f5f5f5;
                        border: 1px solid #e0e0e0;
                        border-radius: 3px;
                        padding: 4px;
                        font-size: 10px;
                        color: #999999;
                    }
                """)
    
    def setAcceptDrops(self, enabled):
        """Override to enable drag and drop on window"""
        super().setAcceptDrops(enabled)
    
    def browse_audio_file(self, filepath=None):
        """Browse for audio file or load from filepath"""
        if filepath:
            self.load_voice_sample(filepath)
        else:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Select Voice Sample (Max 10 seconds)",
                "",
                "Audio files (*.wav *.mp3 *.m4a *.aiff *.flac);;WAV files (*.wav);;MP3 files (*.mp3);;M4A files (*.m4a);;All files (*.*)"
        )
        if filename:
            self.load_voice_sample(filename)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        if event.mimeData().hasUrls():
            filepath = event.mimeData().urls()[0].toLocalFile()
            if filepath:
                self.load_voice_sample(filepath)
            event.acceptProposedAction()
    
    def load_voice_sample(self, filepath, display_name=None):
        """Load and validate voice sample"""
        try:
            
            # Use model interface to validate and convert
            self.status_label.setText("Processing audio file...")
            validated_filepath = validate_audio_file(filepath, max_duration=10.0)
            
            print(f"Validated filepath: {validated_filepath}")
            print(f"Validated file exists: {os.path.exists(validated_filepath)}")
            
            # Get duration for display
            duration = get_audio_duration(validated_filepath)
            
            # Set as current voice sample (overwrites previous)
            self.voice_sample_path = validated_filepath
            
            print(f"Set voice_sample_path to: {self.voice_sample_path}")
            
            # Update UI - hide default label, show file info
            if display_name is None:
                display_name = os.path.basename(validated_filepath)
            
            # Update file name label
            file_text = f"{display_name} ({duration:.1f}s)"
            self.file_name_label.setText(file_text)
            self.drop_label.hide()
            self.file_info_frame.show()
            
            self.status_label.setText(f"Voice sample loaded: {display_name}")
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
            self.status_label.setText(f"Error: {str(e)}")
        except Exception as e:
            print(f"Error loading voice sample: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load audio file:\n{str(e)}")
            self.status_label.setText(f"Error: {str(e)}")
    
    def show_countdown(self, callback):
        """Show countdown popup: first 'recording starts in', then countdown during recording"""
        if self.countdown_window:
            self.countdown_window.close()
        
        self.countdown_window = CountdownDialog(self)
        self.countdown_window.setModal(True)
        
        # First: Countdown "Recording starts in 3, 2, 1"
        def pre_countdown(remaining):
            if remaining > 0:
                self.countdown_window.countdown_label.setText(str(remaining))
                self.countdown_window.countdown_label.setStyleSheet("font-size: 48px; color: #1a1a1a;")
                self.countdown_window.recording_label.setText("Recording starts in")
                self.countdown_window.recording_label.setStyleSheet("font-size: 12px; color: #666666;")
                QTimer.singleShot(1000, lambda: pre_countdown(remaining - 1))
            else:
                # Now start recording and show recording countdown
                self.countdown_window.countdown_label.setText("Go!")
                self.countdown_window.countdown_label.setStyleSheet("font-size: 36px; color: #007AFF;")
                self.countdown_window.recording_label.setText("Recording in progress...")
                self.countdown_window.recording_label.setStyleSheet("font-size: 12px; color: #007AFF;")
                # Start recording and countdown immediately
                callback()
        
        self.countdown_window.show()
        pre_countdown(3)
    
    def record_audio(self):
        """Record 5 seconds of audio from microphone"""
        if self.is_generating:
            QMessageBox.warning(self, "Busy", "Please wait for current operation to complete.")
            return
        
        def start_recording():
            """Start recording and show countdown during recording"""
            # Start countdown during recording (5, 4, 3, 2, 1) - from main thread
            def recording_countdown(remaining):
                if remaining > 0:
                    self.update_countdown_signal.emit(remaining)
                    QTimer.singleShot(1000, lambda: recording_countdown(remaining - 1))
                else:
                    self.update_countdown_signal.emit(0)
            
            # Start the countdown immediately
            recording_countdown(5)
            
            # Start recording in background thread
            def record():
                try:
                    import sounddevice as sd
                    import soundfile as sf
                    
                    # Update UI from main thread using signals
                    self.button_enable_signal.emit(self.record_button, False)
                    self.status_update_signal.emit("Recording... Speak now!")
                    
                    # Create recordings folder in project directory
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    recordings_dir = os.path.join(current_dir, "recordings")
                    os.makedirs(recordings_dir, exist_ok=True)
                    
                    output_file = os.path.join(recordings_dir, f"recorded_{int(time.time())}.wav")
                    print(f"Recording to: {output_file}")
                    
                    # Recording parameters
                    duration = 5  # seconds
                    sample_rate = 24000  # 24kHz
                    channels = 1  # Mono
                    
                    print(f"Recording {duration} seconds at {sample_rate}Hz...")
                    print(f"Available audio devices: {sd.query_devices()}")
                    
                    # Record audio using sounddevice (better permission handling on macOS)
                    recording = sd.rec(
                        int(duration * sample_rate),
                        samplerate=sample_rate,
                        channels=channels,
                        dtype='float32'
                    )
                    
                    # Wait for recording to complete
                    sd.wait()
                    
                    print(f"Recording complete. Max amplitude: {np.max(np.abs(recording))}")
                    
                    # Check if recording has audio
                    if np.max(np.abs(recording)) < 0.001:
                        raise Exception(
                            "Recording appears to be silent!\n\n"
                            "Please check:\n"
                            "1. Microphone is not muted\n"
                            "2. System Settings → Sound → Input → Built-in Microphone volume is up\n"
                            "3. System Settings → Privacy & Security → Microphone permission is granted"
                        )
                    
                    # Save to file
                    sf.write(output_file, recording, sample_rate)
                    
                    file_size = os.path.getsize(output_file)
                    print(f"Saved recording: {file_size} bytes")
                    
                    # Load the recorded file - use signals for thread-safe updates
                    display_name = f"Recorded {time.strftime('%H:%M:%S')}"
                    self.recording_complete_signal.emit(output_file, display_name)
                        
                except FileNotFoundError:
                    self.close_countdown_signal.emit()
                    self.status_update_signal.emit("ERROR: ffmpeg not found. Install with: brew install ffmpeg")
                    self.show_message_signal.emit("Error", "ffmpeg not found. Please install it:\n\nbrew install ffmpeg")
                    self.button_enable_signal.emit(self.record_button, True)
                except Exception as e:
                    self.close_countdown_signal.emit()
                    self.status_update_signal.emit(f"ERROR: Recording failed: {str(e)}")
                    self.show_message_signal.emit("Error", f"Recording failed:\n{str(e)}")
                    self.button_enable_signal.emit(self.record_button, True)
            
            # Start recording thread
            threading.Thread(target=record, daemon=True).start()
        
        # Show countdown first
        self.show_countdown(start_recording)
    
    def generate_and_play(self):
        """Generate audio and play it"""
        if self.is_generating:
            return
        
        if not self.tts:
            QMessageBox.critical(self, "Error", "Model not loaded yet. Please wait.")
            return
        
        if not self.voice_sample_path:
            QMessageBox.critical(self, "Error", "Please select a voice sample or record one first.")
            return
        
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.critical(self, "Error", "Please enter some text to speak.")
            return
        
        def generate():
            self.is_generating = True
            self.play_button.setEnabled(False)
            self.record_button.setEnabled(False)
            
            # Start loading animation
            self.animate_loading(True)
            self.status_label.setText("")
            
            try:
                # Create output directory
                current_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(current_dir, "output")
                os.makedirs(output_dir, exist_ok=True)
                
                # Generate unique output filename
                output_path = os.path.join(output_dir, f"output_{int(time.time())}.wav")
                
                # Collect advanced parameters (None means use model defaults)
                emo_vector = None
                use_emo_text = False
                emo_text = None
                max_mel_tokens = None
                length_penalty = None
                
                # Only collect parameters if in advanced mode
                if self.advanced_mode and hasattr(self, 'advanced_section') and self.advanced_section.isVisible():
                    # Get emotion vector values (only if any are non-zero)
                    if hasattr(self, 'emo_vec_spinboxes') and len(self.emo_vec_spinboxes) == 8:
                        emo_vector = [spinbox.value() for spinbox in self.emo_vec_spinboxes]
                        # Only use if not all zeros (to distinguish from default)
                        if all(v == 0.0 for v in emo_vector):
                            emo_vector = None
                    
                    # Get emotion text settings (only if checkbox is checked)
                    if hasattr(self, 'use_emo_text_checkbox') and self.use_emo_text_checkbox.isChecked():
                        use_emo_text = True
                        if hasattr(self, 'emo_text_input'):
                            emo_text = self.emo_text_input.text().strip()
                            if not emo_text:
                                emo_text = None
                    
                    # Get max mel tokens and length penalty (only if fixed length is enabled)
                    if hasattr(self, 'use_fixed_length_checkbox') and self.use_fixed_length_checkbox.isChecked():
                        if hasattr(self, 'max_mel_tokens_spinbox'):
                            max_mel_tokens = self.max_mel_tokens_spinbox.value()
                        
                        if hasattr(self, 'length_penalty_spinbox'):
                            length_penalty = self.length_penalty_spinbox.value()
                
                # Generate audio using model interface
                generate_speech(
                    self.tts,
                    self.voice_sample_path,
                    text,
                    output_path,
                    emo_vector=emo_vector,
                    use_emo_text=use_emo_text,
                    emo_text=emo_text,
                    max_mel_tokens=max_mel_tokens,
                    length_penalty=length_penalty
                )
                
                # Emit signal - handler will update UI on main thread
                self.generation_complete_signal.emit(output_path)
                
            except Exception as e:
                error_msg = f"Error generating speech: {str(e)}"
                self.generation_error_signal.emit(error_msg)
                print(f"Error: {e}")
        
        threading.Thread(target=generate, daemon=True).start()
    
    def animate_loading(self, start):
        """Animate loading indicator"""
        if start:
            self.loading_dots = 0
            self.loading_active = True
            self.update_loading()
        else:
            self.loading_active = False
            self.loading_label.setText("")
    
    def update_loading(self):
        """Update loading animation"""
        if self.loading_active:
            dots = "." * (self.loading_dots % 4)
            self.loading_label.setText(f"Generating{dots}")
            self.loading_dots += 1
            QTimer.singleShot(200, self.update_loading)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = VoiceCloneApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
