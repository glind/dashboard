"""Lean local speech service for the Yavin personal assistant."""

from __future__ import annotations

import io
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response


app = FastAPI(title="Yavin Local Voice", docs_url=None, redoc_url=None)
_lock = threading.RLock()
_transcriber = None
_tts = None


def get_transcriber():
    global _transcriber
    with _lock:
        if _transcriber is None:
            from moonshine_voice.download import get_model_for_language
            from moonshine_voice.moonshine_api import ModelArch
            from moonshine_voice.transcriber import Transcriber

            model_path, model_arch = get_model_for_language("en", ModelArch.SMALL_STREAMING)
            _transcriber = Transcriber(model_path, model_arch=model_arch)
        return _transcriber


def get_tts():
    global _tts
    with _lock:
        if _tts is None:
            from moonshine_voice.tts import TextToSpeech

            _tts = TextToSpeech("en_us", voice="kokoro_am_michael")
        return _tts


def wav_bytes(samples: list[float], sample_rate: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            value = max(-1.0, min(1.0, float(sample)))
            frames.extend(int(round(value * 32767)).to_bytes(2, "little", signed=True))
        wav.writeframes(frames)
    return output.getvalue()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "engine": "moonshine",
        "stt": "small-streaming",
        "tts": "kokoro_am_michael",
        "transcriber_loaded": _transcriber is not None,
        "tts_loaded": _tts is not None,
    }


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    payload = await audio.read()
    if not payload or len(payload) > 20 * 1024 * 1024:
        raise HTTPException(400, "Audio must be between 1 byte and 20 MB")

    with tempfile.TemporaryDirectory(prefix="yavin-stt-") as temp_dir:
        source = Path(temp_dir) / "input.webm"
        target = Path(temp_dir) / "input.wav"
        source.write_bytes(payload)
        converted = subprocess.run(
            ["/usr/bin/ffmpeg", "-loglevel", "error", "-y", "-i", str(source),
             "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)],
            capture_output=True,
            timeout=30,
        )
        if converted.returncode != 0:
            raise HTTPException(400, "Unsupported or invalid audio recording")

        from moonshine_voice.utils import load_wav_file

        samples, sample_rate = load_wav_file(target)
        with _lock:
            transcript = get_transcriber().transcribe_without_streaming(samples, sample_rate)
        text = " ".join(line.text.strip() for line in transcript.lines if line.text.strip()).strip()
        return {"success": True, "text": text, "engine": "moonshine"}


@app.post("/synthesize")
def synthesize(text: str = Form(...), speed: float = Form(1.0)):
    cleaned = " ".join(text.strip().split())[:5000]
    if not cleaned:
        raise HTTPException(400, "Text is required")
    with _lock:
        samples, sample_rate = get_tts().synthesize(
            cleaned,
            speed=max(0.7, min(1.3, speed)),
        )
    return Response(
        content=wav_bytes(samples, sample_rate),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Voice-Engine": "moonshine-kokoro"},
    )
