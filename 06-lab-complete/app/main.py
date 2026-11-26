"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import signal
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# Tiêu chí 10: Structured JSON logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_obj, ensure_ascii=False)


root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
root_logger.addHandler(handler)

logger = logging.getLogger("agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tiêu chí 11: Lifespan management cho startup và graceful shutdown
    logger.info("Agent starting up...")
    yield
    logger.info("Agent shutting down gracefully...")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(default="", min_length=0, max_length=2000)
    user_id: str | None = None


# Tiêu chí 4: GET /health — liveness: luôn trả 200 khi process còn chạy
@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Tiêu chí 5: GET /ready — readiness: 200 khi sẵn sàng, 503 khi Redis không kết nối được
@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis connection unavailable")
    return {"status": "ready"}


# Tiêu chí 6, 7, 8: POST /ask với Auth, Rate Limiter, Cost Guard
@app.post("/ask")
async def ask(
    request: Request,
    api_key: str = Depends(verify_api_key),
    body: AskRequest | None = None,
):
    check_rate_limit(api_key)
    check_budget()

    question = ""
    if body and body.question:
        question = body.question
    else:
        try:
            raw_json = await request.json()
            if isinstance(raw_json, dict):
                question = raw_json.get("question", "")
        except Exception:
            pass
        if not question:
            question = request.query_params.get("question", "")

    if not question:
        raise HTTPException(status_code=422, detail="question field is required")

    answer = llm_ask(question)

    input_tokens = max(1, len(question) // 4)
    output_tokens = max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens)

    logger.info(json.dumps({
        "event": "ask_success",
        "question_length": len(question),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
    }, ensure_ascii=False))

    return {"question": question, "answer": answer}
