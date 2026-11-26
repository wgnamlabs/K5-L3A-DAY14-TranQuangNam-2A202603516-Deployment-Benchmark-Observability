# Benchmark & Observability Report — Day 14

**Họ tên:** Trần Quang Nam  
**MSSV:** 2A202603516  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows 11 x64, WSL2 (Linux 6.6, Debian 12 / Python 3.11), Docker Desktop (Engine 29.6.2, 4 CPU / 8GB RAM, Redis 7 Alpine, Nginx 1.28 Alpine, Prometheus v3.16.0, Grafana 13.2.4, Jaeger 2.23.0)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Người dùng mong muốn phản hồi nhanh (< 0.5s) cho trải nghiệm tương tác trực tiếp; 500ms cho phép bước retrieval và gọi LLM thông thường diễn ra trôi chảy mà không cảm thấy giật lag. |
| Error rate `/ask` | < 2.0 % | Cho phép dung sai nhỏ trước các lỗi mạng tạm thời hoặc upstream rate limit từ LLM provider, trong khi vẫn bảo đảm 98% request thành công cho người dùng cuối. |
| Accuracy trên golden dataset | ≥ 80.0 % | Đảm bảo chất lượng câu trả lời chuyên môn, bắt buộc không được xảy ra regression trước khi cho phép merge code hoặc deploy lên production. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Số liệu thực tế trích xuất từ các file report tại [reports/](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/):

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 5.11 | 188.6 | 216.7 | 219.6 | 0.5% (1/200) | ✅ PASS |
| 10 | 38.28 | 187.7 | 216.0 | 1663.3 | 1.5% (3/200) | ✅ PASS |
| 50 | 85.24 | 194.0 | 234.9 | 1696.4 | 1.0% (2/200) | ✅ PASS |
| 100 | 87.84 | 250.5 | 775.0 | 1749.4 | 1.5% (3/200) | ❌ FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?
- **Không tăng tuyến tính.** Khi tăng concurrency từ 1 lên 10, RPS tăng mạnh gấp ~7.5 lần (từ 5.11 lên 38.28 RPS) do async event loop của FastAPI tận dụng tốt thời gian chờ I/O của mock LLM.
- Tuy nhiên, khi tăng tiếp lên 50 và 100, RPS tăng chậm dần và chạm ngưỡng bão hòa (~85–88 RPS). Ở mức 100 concurrency, độ trễ xếp hàng (queuing delay) tăng vọt khiến p95 nhảy từ 234.9ms lên 775.0ms (vi phạm SLO), do tài nguyên CPU đơn luồng và giới hạn số connection đồng thời của tiến trình agent đơn lẻ.

### 2.2 Tail latency

Số liệu thực tế từ [load_v2_slow_0.json](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/load_v2_slow_0.json), [load_v2_slow_0.03.json](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/load_v2_slow_0.03.json), và [load_v2_slow_0.1.json](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/load_v2_slow_0.1.json):

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.9 | 218.0 | 219.9 |
| 0.03 (mặc định) | 227.1 | 218.7 | 1690.5 |
| 0.1 | 363.1 | 1688.3 | 1709.3 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?
- **Chỉ số p99 và p95 nhạy nhất với request chậm.** Khi tỷ lệ request chậm chỉ là 3% (`MOCK_SLOW_RATE=0.03`), độ trễ trung bình (avg) chỉ tăng nhẹ từ 189.9ms lên 227.1ms (tăng ~37ms, trông có vẻ rất bình thường). Tuy nhiên p99 lập tức nhảy vọt từ 219.9ms lên 1690.5ms (tăng gấp gần 8 lần)! Đến khi slow rate lên 10%, p95 cũng bị kéo lên tới 1688.3ms.
- **Lý do không dùng average cho SLO:** Giá trị trung bình bị "làm phẳng" bởi 90–97% request nhanh, che giấu hoàn toàn sự thất vọng của 3–10% khách hàng kém may mắn phải chờ gần 2 giây. Đo lường theo percentile (p95, p99) phản ánh chính xác rủi ro trải nghiệm người dùng thực tế tại đuôi phân phối (tail latency).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Số liệu thực tế trích xuất từ [eval_v1.json](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/eval_v1.json), [eval_v2.json](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/eval_v2.json), và [eval_v2_fixed.json](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/reports/eval_v2_fixed.json):

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 56.2 | 108.8 | 112.6 |
| Tổng cost (USD) | $0.000391 | $0.000757 | $0.000781 |
| Cost / câu đúng (USD) | $0.00039135 | $0.00003607 | $0.00003397 |
| Quality gate | ❌ FAIL | ✅ PASS (+87.0% vs v1) | ✅ PASS (100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` entry: `(["jwt", "api key", "xác thực"], "JWT (JSON Web Token) là token tự chứa claims, có cơ chế hết hạn và được bảo vệ bằng chữ ký số, khác với API key là chuỗi tĩnh.")` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` entry: `(["hpa", "kubernetes", "scale"], "Kubernetes HPA (Horizontal Pod Autoscaler) tự động scale pod dựa trên CPU, memory hoặc custom metrics thu thập từ ứng dụng.")` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- **Chất lượng tăng vọt:** Agent v2 sử dụng kiến trúc RAG (retrieval-augmented generation), tra cứu knowledge base trước khi đưa vào context để trả lời, nâng accuracy từ 4.3% lên 91.3% và đạt 100.0% sau khi bổ sung tri thức.
- **Trade-off chi phí:** v2 tiêu tốn số token gấp đôi v1 (112.6 vs 56.2 tokens/câu) vì phải nhồi thêm context vào prompt. Tuy nhiên, tính theo **chi phí trên mỗi câu trả lời đúng (cost per correct answer)**, v2 lại rẻ hơn v1 hơn 11.5 lần ($0.00003397 so với $0.00039135 USD), vì v1 hầu hết trả lời sai nên mọi token tiêu tốn đều là lãng phí.
- **Trade-off latency:** v2 tốn thêm khoảng 20ms cho bước tra cứu context vector/keyword, nhưng đây là mức đánh đổi hoàn toàn xứng đáng để có câu trả lời chính xác 100%.

---

## 4. Observability stack (production)

### 4.1 Screenshot

Tất cả ảnh chụp màn hình được lưu trong thư mục [screenshots/](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/):

- [x] Dashboard Grafana khi đang có tải: [grafana-dashboard.png](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/grafana-dashboard.png) (thấy rõ 4 Golden Signals, RPS, Latency, Token/s và Cost/h)
- [x] Một trace chậm trong Jaeger: [jaeger-slow-trace.png](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/jaeger-slow-trace.png) (span `chat mock-llm-small` chiếm 98.8% thời gian)
- [x] Một trace lỗi trong Jaeger: [jaeger-error-trace.png](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/jaeger-error-trace.png) (span có event `exception` 503 upstream)
- [x] Trang Alerts của Prometheus: [prometheus-alert-firing.png](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/screenshots/prometheus-alert-firing.png) (alert `AgentInstanceDown` và `LLMCostBurnRateHigh` đang **firing**)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~60 giây (ngưỡng error rate > 5%, `for: 1m`) | Panel **Error rate** (đỏ rực > 20%) và biểu đồ req/s theo status. |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~120 giây (ngưỡng p95 > 1s, `for: 2m`) | Panel **p95 Latency** và khoảng cách giữa avg và p99 (tail latency gap). |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~120 giây (ngưỡng > $2/giờ, `for: 2m`) | Panel **Cost USD / giờ** tăng vọt gấp ~16 lần lên trên $5–$10/h. |
| D | `docker pause production-agent-1` | `AgentInstanceDown` | 30 giây (ngưỡng `up == 0`, `for: 30s`) | Panel **Instances UP** (giảm còn 1) và biểu đồ Traffic theo instance. |
| E | `AGENT_VERSION=v1` | *(Không có alert nào firing)* | N/A | Panel **Retrieval Hit Ratio** mất đi, tokens/s giảm, bảng version đổi. |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
- Sự cố chất lượng nội dung (Quality Regression) không làm tăng lỗi HTTP (vẫn trả về 200 OK) và thậm chí còn làm giảm latency (vì v1 không mất thời gian retrieval). Do đó các công cụ giám sát hạ tầng truyền thống (CPU, RAM, HTTP metrics) hoàn toàn mù trước loại lỗi này.
- Để phát hiện trong production, cần kết hợp:
  1. **Continuous Evaluation Pipeline:** Chạy tự động bộ test golden dataset trong CI/CD trước khi cho phép deploy bất kỳ commit/prompt/model mới nào (như bài test `run_eval.py --baseline`).
  2. **Production Sampling & LLM-as-a-judge:** Định kỳ lấy mẫu 1–5% logs câu trả lời thực tế của người dùng và cho model giám sát đánh giá độ chính xác, format và mức độ hữu ích.
  3. **User Feedback Signals (Implicit & Explicit):** Theo dõi tỷ lệ người dùng nhấn Thumbs Down, tỷ lệ hỏi lại ngay lập tức (retry/rephrase query) hoặc hủy phiên hội thoại bất thường.

### 4.3 Debug bằng trace

Chi tiết từ trace thực tế thu được trong quá trình load test:

- `trace_id`: `d9d696e3a4866f6ca952ad8d329fe978`
- Tổng thời gian: `1718.5` ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1698.4` ms, chiếm `98.8%` tổng thời lượng request)
- Dòng log tương ứng trong hệ thống (grep theo `trace_id`):

```json
{"ts": "2026-11-25T13:58:25.535598+00:00", "level": "INFO", "service": "observable-agent", "instance": "95cbe825bcd3", "event": "llm_call", "trace_id": "d9d696e3a4866f6ca952ad8d329fe978", "span_id": "047c4ac352c24f17", "request_id": "f3596b370101", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1698.4}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu thực tế trích xuất từ file [benchmark-results/scale_1_stats.csv](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/benchmark-results/scale_1_stats.csv) và [benchmark-results/scale_3_stats.csv](file:///D:/K5-L3A-DAY14-TranQuangNam-2A202603516-Deployment-Benchmark-Observability/benchmark-results/scale_3_stats.csv):

| Số instance | RPS (/ask) | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59.87 req/s (Agg: 65.93) | 190 | 230 | 1700 | 81 (1.03%) |
| 3 | 59.89 req/s (Agg: 65.65) | 190 | 220 | 1700 | 68 (0.88%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?
- **Scale không làm thay đổi đáng kể RPS hay p95/p99:** Khi scale từ 1 lên 3 instance, throughput `/ask` giữ nguyên ở mức ~59.9 req/s, p50 giữ nguyên ở 190ms, p95 dao động từ 230ms về 220ms, và p99 giữ nguyên ở 1700ms.
- **Nút thắt nằm ở đâu?** Nút thắt chính là **Upstream LLM Latency** (mô phỏng cuộc gọi ra dịch vụ AI bên ngoài như OpenAI/Anthropic có độ trễ cơ bản 120–180ms kèm 3% tail latency 1.7s). Mỗi người dùng giả lập của Locust có thời gian nghỉ giữa các câu hỏi (`wait_time = between(0.5, 2)`), do đó 100 user phân tán không gây nghẽn CPU hay bộ nhớ trên 1 node agent FastAPI (xử lý I/O bất đồng bộ non-blocking). Việc scale ngang nhiều replica giúp tăng trần chịu tải tối đa (capacity ceiling) khi hàng nghìn người cùng gửi request dồn dập, nhưng **không thể làm giảm độ trễ bản chất của từng cuộc gọi LLM**.

---

## 6. Kết luận

- **3 điều quan trọng học được về benchmark & observability:**
  1. **Percentile (p95, p99) là chân lý, không bao giờ tin vào average:** Trung bình luôn che giấu các spike và tail latency gây ức chế cho người dùng. Mọi SLO và Alert phải căn cứ theo percentile.
  2. **Observability ba trụ cột (Metrics - Traces - Logs) phải được liên kết chặt chẽ:** Metrics phát hiện có bất thường (Alert firing) → Dashboard thu hẹp phạm vi → Jaeger Trace định vị span bị nghẽn → `trace_id` dẫn thẳng tới JSON log để biết nguyên nhân gốc rễ (Root Cause Analysis).
  3. **Benchmarking chất lượng (Eval) quan trọng ngang ngửa benchmark hiệu năng:** Đổi prompt hay model có thể giữ hạ tầng xanh mượt nhưng câu trả lời lại hoàn toàn sai lệch. Golden dataset và automated eval gate là chốt chặn bắt buộc trong CI/CD.
- **Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?**
  1. *LLM Token Quota & Throttling Rate:* Đo lường số lần bị OpenAI/Anthropic trả lỗi 429 Rate Limit theo phút/ngày.
  2. *Cache Hit Ratio:* Đo lường tỷ lệ các câu hỏi lặp lại được trả lời từ Redis semantic cache mà không cần tốn tiền gọi lại LLM.
  3. *Cost Burn Rate Projections:* Alert dự báo ngân sách tự động cắt giảm lưu lượng hoặc fallback về model giá rẻ khi chi tiêu trong ngày đạt 80% hạn mức.
  4. *Circuit Breaker Alert:* Cảnh báo khi upstream LLM sập quá 50% trong 30s để hệ thống tự chuyển sang chế độ degraded mode (trả lời câu hỏi có sẵn hoặc thông báo bảo trì thân thiện).
