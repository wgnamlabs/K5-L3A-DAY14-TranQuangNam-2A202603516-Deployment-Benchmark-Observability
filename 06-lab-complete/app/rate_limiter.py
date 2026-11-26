"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    now = time.time()
    redis_key = f"ratelimit:{key}"
    window = 60

    try:
        # Xóa các request ngoài cửa sổ trượt 60 giây
        r.zremrangebyscore(redis_key, 0, now - window)
        count = r.zcard(redis_key)
        if count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"},
            )
        # Ghi nhận request mới
        r.zadd(redis_key, {str(now): now})
        r.expire(redis_key, window)
    except HTTPException:
        raise
    except Exception:
        # Không chặn nếu Redis tạm thời gặp lỗi
        pass
