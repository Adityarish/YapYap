import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import queue
import threading
import time
import torch

# -------------------------
# CONFIG
# -------------------------
SAMPLE_RATE = 16000
BLOCK_DURATION = 0.5  # seconds per chunk
MODEL_SIZE = "small"  # use "medium" or "large-v3" if you have more VRAM
OUTPUT_FILE = "final_transcript.txt"
CHUNK_SECONDS = 4      # Transcribe every 4 seconds

# -------------------------
# DEVICE CONFIGURATION
# -------------------------
if torch.cuda.is_available():
    DEVICE = "cuda"
    COMPUTE_TYPE = "float16"  # Best balance of performance and accuracy for NVIDIA GPUs
else:
    DEVICE = "cpu"
    COMPUTE_TYPE = "int8"     # fallback
print(f"Using device: {DEVICE} ({COMPUTE_TYPE})")

# -------------------------
# LOAD MODEL
# -------------------------
print("Loading Whisper model... (this may take a few seconds)")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)

audio_queue = queue.Queue()
stop_flag = False

# -------------------------
# AUDIO CALLBACK
# -------------------------
def audio_callback(indata, frames, time_data, status):
    if status:
        print("Audio status:", status)
    audio_queue.put(indata.copy())

# -------------------------
# TRANSCRIPTION THREAD
# -------------------------
def transcribe_audio():
    print("Transcription thread started.")
    audio_buffer = np.zeros((0, 1), dtype=np.float32)

    while not stop_flag:
        try:
            chunk = audio_queue.get(timeout=1)
            audio_buffer = np.concatenate((audio_buffer, chunk))

            # Process every few seconds
            if len(audio_buffer) >= SAMPLE_RATE * CHUNK_SECONDS:
                temp = audio_buffer.flatten().astype(np.float32)
                audio_buffer = np.zeros((0, 1), dtype=np.float32)  # reset early

                # Transcribe
                segments, info = model.transcribe(
                    temp,
                    beam_size=1,          # 1 = faster, increase for better accuracy
                    vad_filter=True,      # helps remove silence/noise segments
                    language="en",        # set manually for speed (skip autodetect)
                )

                # Write output
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    for seg in segments:
                        text = seg.text.strip()
                        if text:
                            print(">>", text)
                            f.write(text + "\n")

        except queue.Empty:
            continue

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    print("🎤 START SPEAKING... (Press Ctrl+C to stop)")

    transcriber_thread = threading.Thread(target=transcribe_audio, daemon=True)
    transcriber_thread.start()

    try:
        with sd.InputStream(callback=audio_callback, channels=1, samplerate=SAMPLE_RATE, dtype='float32'):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        stop_flag = True
        print("\nStopping...")
        time.sleep(1)

    print("✅ Transcript saved to:", OUTPUT_FILE)
