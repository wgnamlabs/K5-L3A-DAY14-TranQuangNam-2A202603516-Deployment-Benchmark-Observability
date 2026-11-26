# Deployment Information

## Public URL
`https://ai-agent-prod-day14.up.railway.app`

*(Dự phòng Render: `https://ai-agent-prod-day14.onrender.com`)*

## Platform
- **Primary Platform:** Railway (sử dụng [railway.toml](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/06-lab-complete/railway.toml))
- **Secondary Platform:** Render (sử dụng Infrastructure as Code [render.yaml](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/06-lab-complete/render.yaml))
- **Architecture:** Multi-stage Docker container (`python:3.11-slim`, non-root user `appuser`, image size 56 MB) + Managed Redis 7 Alpine.

---

## Test Commands

Đặt biến môi trường để test:
```bash
BASE="https://ai-agent-prod-day14.up.railway.app"
AGENT_API_KEY="day14-secret-key"
```

### 1. Health Check (Liveness Probe)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Kết quả mong đợi: 200
```
Chi tiết response:
```bash
curl -s "$BASE/health" | python -m json.tool
# Response:
# {
#     "status": "ok",
#     "environment": "production",
#     "uptime_seconds": 1248.5
# }
```

### 2. Readiness Check (Readiness Probe)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Kết quả mong đợi: 200 (nếu Redis down trả về 503 Service Unavailable)
```

### 3. API Test - Từ chối khi thiếu hoặc sai API Key (401 Unauthorized)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Kết quả mong đợi: 401
```

### 4. API Test - Thành công với đúng API Key (200 OK)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"What is the purpose of readiness probe?"}'
# Kết quả mong đợi: 200
```
Chi tiết response JSON đầy đủ:
```bash
curl -s -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"What is the purpose of readiness probe?"}' | python -m json.tool

# Response:
# {
#     "answer": "Readiness probe (GET /ready) cho biết instance sẵn sàng nhận traffic. Nếu fail, load balancer ngừng route traffic tới instance đó nhưng không restart container.",
#     "model": "mock-llm-small",
#     "agent_version": "v2",
#     "usage": {
#         "input_tokens": 74,
#         "output_tokens": 37,
#         "cost_usd": 0.0000333
#     },
#     "llm_latency_ms": 178.4,
#     "request_id": "c8b91a27e0f4"
# }
```

---

## Environment Variables Set

Các biến môi trường được cấu hình an toàn trên Railway / Render Dashboard (không hardcode vào mã nguồn):

| Biến môi trường | Giá trị ví dụ | Mục đích |
|---|---|---|
| `PORT` | `8000` | Port lắng nghe do nền tảng cấp tự động |
| `ENVIRONMENT` | `production` | Môi trường triển khai |
| `AGENT_API_KEY` | `day14-secret-key` | Khóa xác thực API client (Header `X-API-Key`) |
| `REDIS_URL` | `redis://redis.railway.internal:6379/0` | Kết nối Redis nội bộ để lưu sliding window rate limiter và cost budget |
| `RATE_LIMIT_PER_MINUTE` | `10` | Giới hạn 10 requests / phút / client |
| `DAILY_BUDGET_USD` | `10.0` | Ngân sách chi tiêu LLM tối đa trong ngày ($10 USD) |
| `MONTHLY_BUDGET_USD` | `100.0` | Ngân sách chi tiêu LLM tối đa trong tháng ($100 USD) |

---

## Screenshots

- [Deployment Dashboard](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/dashboard.png): Giao diện tổng quan dịch vụ triển khai và trạng thái Active.
- [Service Running & Health](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/running.png): Runtime logs, kết nối Redis, tiến trình Uvicorn và HTTP 200 healthcheck.
- [Test Results](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/test.png): Kết quả chạy test trực tiếp các lệnh `curl` với mã phản hồi 200, header rate limit và JSON payload.
