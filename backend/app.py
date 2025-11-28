import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

import numpy as np
import sounddevice as sd
import torch
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from TextProcessing.preprocessing import ChunkPreprocessor


# -------------------------
# CONFIGURATION
# -------------------------
SAMPLE_RATE = 16_000
BLOCK_DURATION = 0.5  # seconds per chunk
MODEL_SIZE = "small"
CHUNK_SECONDS = 6
MAX_HISTORY = 200

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent
FRONTEND_DIR = BASE_DIR / "frontend"
EXTENSION_DIR = BASE_DIR / "realtime-stt-extension"
OUTPUT_FILE = BACKEND_DIR / "final_transcript.txt"
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)
PORT = int(os.getenv("PORT", "5000"))


# -------------------------
# DEVICE CONFIGURATION
# -------------------------
if torch.cuda.is_available():
    DEVICE = "cuda"
    COMPUTE_TYPE = "float16"
else:
    DEVICE = "cpu"
    COMPUTE_TYPE = "int8"

print(f"Using device: {DEVICE} ({COMPUTE_TYPE})")
print("Loading Whisper model... (this may take a few seconds)")
print(f"Backend will listen on port: {PORT}")


def _sync_client_configs(port: int) -> None:
    frontend_config = FRONTEND_DIR / "app-config.js"
    extension_config = EXTENSION_DIR / "config.js"
    base_url = f"http://localhost:{port}"

    frontend_payload = (
        "window.APP_CONFIG = Object.assign(\n"
        "  {},\n"
        "  window.APP_CONFIG || {},\n"
        f"  {{ API_BASE_URL: \"{base_url}\" }}\n"
        ");\n"
    )
    extension_payload = (
        "self.YAPYAP_CONFIG = Object.assign(\n"
        "  {},\n"
        "  self.YAPYAP_CONFIG || {},\n"
        f"  {{ backendBaseUrl: \"{base_url}\" }}\n"
        ");\n"
    )

    try:
        frontend_config.write_text(frontend_payload, encoding="utf-8")
        extension_config.write_text(extension_payload, encoding="utf-8")
    except OSError as exc:
        print(f"Warning: unable to sync client config files: {exc}")


_sync_client_configs(PORT)


# -------------------------
# GLOBAL STATE
# -------------------------
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
transcriber = None  # initialized after class definitions

audio_queue: "queue.Queue[np.ndarray]" = queue.Queue()
stop_event = threading.Event()

history_lock = threading.Lock()
RESULT_HISTORY: "deque[Dict[str, object]]" = deque(maxlen=MAX_HISTORY)

audio_thread: Optional[threading.Thread] = None
transcribe_thread: Optional[threading.Thread] = None
capture_active = False


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


def _round_ms(value: float) -> float:
    return round(value, 3)


@dataclass
class TranscriptionResult:
    text: str
    raw_latency_ms: float
    processed_latency_ms: float
    preprocessing_ms: Dict[str, float]


class RealTimeTranscriber:
    def __init__(
        self,
        whisper_model: WhisperModel,
        *,
        chunk_duration: int = CHUNK_SECONDS,
        preprocessor_factory: Callable[[], ChunkPreprocessor] | None = None,
    ) -> None:
        self.model = whisper_model
        self.chunk_duration = chunk_duration
        self.preprocessor = (
            preprocessor_factory() if preprocessor_factory else ChunkPreprocessor()
        )

    def _post_process(self, text: str) -> tuple[str, Dict[str, float]]:
        processed = self.preprocessor(text)
        timings = dict(processed.pop("timings_ms", {}))
        return processed["final"], timings

    def transcribe(self, audio: np.ndarray) -> list[TranscriptionResult]:
        t_start = time.time()
        segments, _info = self.model.transcribe(
            audio,
            beam_size=1,
            vad_filter=True,
            language="en",
        )
        decode_latency = _round_ms((time.time() - t_start) * 1000)

        results: list[TranscriptionResult] = []
        for seg in segments:
            original_text = seg.text.strip()
            if not original_text:
                continue

            t_proc = time.time()
            final_text, timings = self._post_process(original_text)
            process_latency = _round_ms((time.time() - t_proc) * 1000)

            timings = {k: _round_ms(v) for k, v in timings.items()}
            results.append(
                TranscriptionResult(
                    text=final_text,
                    raw_latency_ms=decode_latency,
                    processed_latency_ms=process_latency,
                    preprocessing_ms=timings,
                )
            )

        return results


transcriber = RealTimeTranscriber(model)


def audio_callback(indata, frames, time_data, status):
    if status:
        print("Audio status:", status)
    audio_queue.put(indata.copy())


def _persist_results(results: list[TranscriptionResult]) -> None:
    if not results:
        return

    with open(OUTPUT_FILE, "a", encoding="utf-8") as file_handle:
        for res in results:
            timestamp = _now_iso()
            preprocess_timings = dict(res.preprocessing_ms)
            preprocess_total = _round_ms(sum(preprocess_timings.values()))

            record = {
                "id": f"{timestamp}-{time.time_ns()}",
                "text": res.text,
                "timestamp": timestamp,
                "raw_latency_ms": res.raw_latency_ms,
                "processed_latency_ms": res.processed_latency_ms,
                "preprocessing_ms": preprocess_timings,
                "preprocessing_total_ms": preprocess_total,
            }

            telemetry = (
                f"raw={res.raw_latency_ms}ms, "
                f"processing={res.processed_latency_ms}ms, "
                f"details={preprocess_timings}"
            )
            print(f"» {res.text} ({telemetry})")
            file_handle.write(res.text + "\n")

            with history_lock:
                RESULT_HISTORY.append(record)


def transcribe_audio_loop() -> None:
    print("Transcription thread started.")
    audio_buffer = np.zeros((0, 1), dtype=np.float32)

    while not stop_event.is_set():
        try:
            chunk = audio_queue.get(timeout=1)
        except queue.Empty:
            if stop_event.is_set():
                break
            continue

        audio_buffer = np.concatenate((audio_buffer, chunk))

        if len(audio_buffer) >= SAMPLE_RATE * CHUNK_SECONDS:
            temp = audio_buffer.flatten().astype(np.float32)
            audio_buffer = np.zeros((0, 1), dtype=np.float32)

            results = transcriber.transcribe(temp)
            _persist_results(results)


def audio_stream_loop() -> None:
    global capture_active
    try:
        with sd.InputStream(
            callback=audio_callback,
            channels=1,
            samplerate=SAMPLE_RATE,
            dtype="float32",
        ):
            capture_active = True
            print("🎤 Audio stream active (Ctrl+C to stop).")
            while not stop_event.is_set():
                time.sleep(0.1)
    except Exception as exc:  # pylint: disable=broad-except
        capture_active = False
        print(f"Audio stream error: {exc}")
        stop_event.set()
    finally:
        capture_active = False


def _clear_audio_queue() -> None:
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
        except queue.Empty:
            break


def start_pipeline() -> None:
    global audio_thread, transcribe_thread
    if capture_active:
        return

    stop_event.clear()
    _clear_audio_queue()

    audio_thread = threading.Thread(target=audio_stream_loop, daemon=True)
    transcribe_thread = threading.Thread(target=transcribe_audio_loop, daemon=True)

    audio_thread.start()
    transcribe_thread.start()


def stop_pipeline() -> None:
    stop_event.set()
    _clear_audio_queue()

    for worker in (audio_thread, transcribe_thread):
        if worker and worker.is_alive():
            worker.join(timeout=2)


def get_status() -> Dict[str, object]:
    with history_lock:
        history_length = len(RESULT_HISTORY)
        latest = RESULT_HISTORY[-1] if history_length else None

    return {
        "capture_active": capture_active and not stop_event.is_set(),
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "sample_rate": SAMPLE_RATE,
        "chunk_seconds": CHUNK_SECONDS,
        "history_size": history_length,
        "latest": latest,
    }


# -------------------------
# FASTAPI APPLICATION
# -------------------------
app = FastAPI(title="Speech2Text Monitor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.on_event("startup")
async def on_startup() -> None:
    start_pipeline()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_pipeline()


@app.get("/api/status")
async def api_status() -> Dict[str, object]:
    return get_status()


@app.get("/api/transcripts")
async def api_transcripts(limit: int = 50) -> Dict[str, object]:
    limit = max(1, min(limit, MAX_HISTORY))
    with history_lock:
        items = list(RESULT_HISTORY)[-limit:]

    paragraph = " ".join(entry["text"].strip() for entry in items if entry.get("text")).strip()
    current = items[-1] if items else None

    return {
        "paragraph": paragraph,
        "current": current,
        "items": items,
        "count": len(items),
    }


class ControlRequest(BaseModel):
    action: str


@app.post("/api/control")
async def api_control(payload: ControlRequest) -> Dict[str, object]:
    action = (payload.action or "").lower()

    if action == "start":
        start_pipeline()
    elif action == "stop":
        stop_pipeline()
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    return get_status()


@app.get("/")
async def index() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    return FileResponse(index_path)


@app.get("/api/extension/latest")
async def api_extension_latest() -> Dict[str, object]:
    with history_lock:
        latest = RESULT_HISTORY[-1] if RESULT_HISTORY else None

    if not latest:
        return {"id": None, "text": "", "timestamp": None}

    return {
        "id": latest.get("id"),
        "text": latest.get("text", ""),
        "timestamp": latest.get("timestamp")
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)
