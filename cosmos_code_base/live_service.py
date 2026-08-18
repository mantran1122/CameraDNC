"""
Cosmos Live Service — FastAPI wrapper cho single-frame inference.

Chạy:
    python live_service.py [--model-id ...] [--gpu-memory-utilization 0.85] [--port 8765]

Server start ngay lập tức. Model load trong background thread.
GET /health trả {"status": "loading"} ngay khi server còn đang load model.
"""

import argparse
import io
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Config điền trong main() trước khi uvicorn.run
_cfg: dict = {}

# Runtime state — đọc/ghi dưới _status_lock
_status_lock = threading.Lock()
_status = "loading"
_status_detail: str | None = None

# Model — chỉ ghi 1 lần trong _load_model()
_model = None
_processor = None
_sampling_params = None

# Đảm bảo không có 2 inference chạy cùng lúc
_inference_lock = threading.Lock()

# JSON schema cho guided_json của vllm — bắt model xuất đúng cấu trúc
_LIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["none", "low", "medium", "high"]},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "count": {"type": "integer", "minimum": 0},
                },
                "required": ["label", "count"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "risk_level", "events"],
    "additionalProperties": False,
}

_LIVE_PROMPT = """\
You are a real-time surveillance camera analyst. You receive a single camera frame.

Analyze the frame and return ONLY valid JSON — no markdown, no explanation, no extra text.

JSON schema:
{
  "summary": "<Vietnamese description — concise, operational, what you see>",
  "risk_level": "<none|low|medium|high>",
  "events": [
    {"label": "<object type in Vietnamese>", "count": <integer estimate>}
  ]
}

risk_level:
- none: empty or completely normal, nothing to flag
- low: people present, normal activity, mild crowding
- medium: clear phone usage, crowding, suspicious behavior, unattended objects
- high: fight, fall, intrusion, fire, smoke, theft, immediate safety threat

events: list every significant object type you see (nguoi, xe_may, o_to, xe_tai, ba_lo, tui_xach, ...).
Count is an estimate — VLM counts are approximate, not exact.
summary: Vietnamese, 1-2 sentences, what is happening and where.

Return JSON only."""


def _set_status(status: str, detail: str | None = None) -> None:
    global _status, _status_detail
    with _status_lock:
        _status = status
        _status_detail = detail


def _get_status() -> tuple[str, str | None]:
    with _status_lock:
        return _status, _status_detail


def _load_model() -> None:
    global _model, _processor, _sampling_params

    model_id = _cfg["model_id"]
    gpu_util = _cfg["gpu_memory_utilization"]
    max_model_len = _cfg["max_model_len"]
    max_new_tokens = _cfg["max_new_tokens"]

    try:
        from transformers import AutoProcessor

        logger.info("Loading processor: %s", model_id)
        _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

        try:
            from vllm import LLM, SamplingParams
        except ImportError as exc:
            raise RuntimeError(
                "vllm không tìm thấy. Cài: pip install vllm  (cần CUDA)."
            ) from exc

        logger.info(
            "Loading vLLM model: %s  gpu_util=%.2f  max_model_len=%d",
            model_id, gpu_util, max_model_len,
        )
        _model = LLM(
            model=model_id,
            trust_remote_code=True,
            dtype="auto",
            gpu_memory_utilization=float(gpu_util),
            max_model_len=max_model_len,
            limit_mm_per_prompt={"image": 1},
        )

        try:
            # vLLM 0.23+ renamed guided_json to structured_outputs.  Use the
            # current API so the model is constrained to the response schema.
            from vllm.sampling_params import StructuredOutputsParams

            _sampling_params = SamplingParams(
                temperature=0.0,
                max_tokens=max_new_tokens,
                structured_outputs=StructuredOutputsParams(json=_LIVE_SCHEMA),
            )
            logger.info("JSON structured output enabled.")
        except (ImportError, TypeError) as exc:
            # Keep compatibility with older vLLM releases, although those
            # releases cannot guarantee a parseable JSON response.
            logger.warning("JSON structured output unavailable: %s", exc)
            _sampling_params = SamplingParams(
                temperature=0.0, max_tokens=max_new_tokens
            )

        _set_status("ready")
        logger.info("Model ready.")

    except Exception as exc:
        _set_status("error", str(exc))
        logger.error("Model load failed: %s", exc)


def _build_prompt_text(image: Image.Image) -> str:
    """Tạo prompt string theo chat template nếu processor hỗ trợ."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": _LIVE_PROMPT},
            ],
        }
    ]
    if hasattr(_processor, "apply_chat_template"):
        try:
            return _processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            pass
    return _LIVE_PROMPT


def _run_inference(image: Image.Image) -> str:
    """Chạy inference, trả về chuỗi JSON (chưa parse)."""
    prompt_text = _build_prompt_text(image)
    request = {
        "prompt": prompt_text,
        "multi_modal_data": {"image": [image]},
    }
    outputs = _model.generate([request], _sampling_params)
    output_text = outputs[0].outputs[0].text if outputs and outputs[0].outputs else ""

    # Trích JSON nếu model thêm text thừa bên ngoài
    start = output_text.find("{")
    end = output_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return output_text[start : end + 1]
    return output_text.strip()


# ── FastAPI app ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    t = threading.Thread(target=_load_model, daemon=True, name="model-loader")
    t.start()
    yield


app = FastAPI(title="Cosmos Live Service", version="1.0", lifespan=_lifespan)


@app.get("/health")
async def health():
    status, detail = _get_status()
    if status == "error":
        return JSONResponse({"status": "error", "detail": detail})
    return {"status": status}


@app.post("/analyze")
def analyze(body: bytes = Body(..., media_type="application/octet-stream")):
    """
    Nhận JPEG bytes, trả JSON phân tích.
    Endpoint là def thường (không async) để uvicorn đẩy vào threadpool —
    tránh block event loop suốt thời gian inference (~4s).
    """
    status, detail = _get_status()
    if status != "ready":
        return JSONResponse(
            {"status": "error", "detail": f"service not ready: {status}"},
            status_code=503,
        )

    # Drop frame nếu model đang bận với frame trước
    if not _inference_lock.acquire(blocking=False):
        return JSONResponse({"status": "error", "detail": "busy"}, status_code=429)

    try:
        t0 = time.perf_counter()

        try:
            image = Image.open(io.BytesIO(body)).convert("RGB")
        except Exception as exc:
            return JSONResponse(
                {"status": "error", "detail": f"invalid image: {exc}"},
                status_code=400,
            )

        try:
            result_text = _run_inference(image)
        except Exception as exc:
            logger.error("Inference error: %s", exc)
            return JSONResponse(
                {"status": "error", "detail": str(exc)},
                status_code=500,
            )

        inference_ms = int((time.perf_counter() - t0) * 1000)

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed: %s | raw: %.200s", exc, result_text)
            return JSONResponse(
                {"status": "error", "detail": f"model output parse failed: {exc}"},
                status_code=500,
            )

        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "inference_ms": inference_ms,
            "result": result,
        }

    finally:
        _inference_lock.release()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cosmos Live Service")
    parser.add_argument(
        "--model-id",
        default="nvidia/Cosmos-Reason2-2B",
        help="HuggingFace model ID (default: nvidia/Cosmos-Reason2-2B)",
    )
    parser.add_argument(
        "--gpu-memory-utilization",
        type=float,
        default=0.85,
        metavar="FLOAT",
        help="Phần VRAM dành cho vllm, ví dụ 0.85 (default: 0.85 — benchmark để chốt)",
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=8192,
        help="Max context length (default: 8192 — đủ cho 1 frame)",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=512,
        help="Max tokens model sinh ra (default: 512)",
    )
    parser.add_argument("--hf-token", default=None, metavar="TOKEN",
                        help="HuggingFace access token cho gated model (hf_xxx...)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not 0 < args.gpu_memory_utilization <= 1:
        parser.error("--gpu-memory-utilization phải trong khoảng (0, 1]")

    if args.hf_token:
        try:
            from huggingface_hub import login as hf_login
            hf_login(token=args.hf_token, add_to_git_credential=False)
            logger.info("HuggingFace login OK.")
        except Exception as exc:
            logger.warning("HuggingFace login failed: %s", exc)

    _cfg.update(
        {
            "model_id": args.model_id,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "max_model_len": args.max_model_len,
            "max_new_tokens": args.max_new_tokens,
        }
    )

    logger.info(
        "Cosmos Live Service  host=%s  port=%d  model=%s  gpu_util=%.2f",
        args.host, args.port, args.model_id, args.gpu_memory_utilization,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
