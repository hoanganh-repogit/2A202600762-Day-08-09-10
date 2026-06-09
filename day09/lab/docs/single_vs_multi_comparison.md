# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Ngũ Hổ Tướng  
**Ngày:** 09/06/2026  
**Trace batch Day 09:** `eval_20260609_114716_162914`

> Không có artifact Day 08 trong repo hiện tại, nên các ô Day 08 được ghi `N/A` thay vì bịa số liệu. Phần kết luận dựa trên số liệu thật của Day 09 và khác biệt kiến trúc quan sát được từ trace.

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|------------------------|-----------------------|-------|---------|
| Route accuracy | N/A | 15/15 = 100% | N/A | So với `expected_route` trong `test_questions.json` |
| Source coverage | N/A | 15/15 = 100% | N/A | Expected sources đều là subset của `retrieved_sources` |
| Avg confidence | N/A | 0.871 | N/A | Từ `artifacts/eval_report.json` |
| Avg latency | N/A | 1 ms | N/A | Offline retrieval + deterministic synthesis |
| Abstain/HITL rate | N/A | 1/15 = 6% | N/A | q09 `ERR-403-AUTH` |
| MCP usage rate | N/A | 6/15 = 40% | N/A | Policy/access/refund decision routes |
| Routing visibility | Không có trong kiến trúc single-agent | Có `route_reason`, `workers_called`, `worker_io_logs` | Có lợi cho debug | Bằng chứng trực tiếp trong trace JSON |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy/source coverage | N/A | 9/9 retrieval-style câu route/source đúng |
| Latency | N/A | Khoảng 0-1 ms/câu retrieval |
| Observation | N/A | Retrieval offline trả source sạch: q01 `sla_p1_2026.txt`, q05 `hr_leave_policy.txt`, q04 `it_helpdesk_faq.txt` |

**Kết luận:** Với KB nhỏ, multi-agent không làm chậm đáng kể vì supervisor và retrieval đều rule-based. Lợi ích chính là trace rõ worker nào chịu trách nhiệm.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy/source coverage | N/A | q13 và q15 đều retrieve đủ `sla_p1_2026.txt` + `access_control_sop.txt` |
| Routing visible? | Không có trong single-agent baseline | Có |
| Observation | N/A | q15 gọi `search_kb`, `check_access_permission`, `get_ticket_info` rồi synthesis trả cả hai quy trình |

**Kết luận:** Multi-agent hữu ích nhất ở multi-hop vì policy worker có thể gọi MCP để kiểm tra access rule, trong khi retrieval worker vẫn đảm bảo source cite sạch.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | N/A | 1/15 |
| Hallucination cases | N/A | 0 quan sát được trên q09 |
| Observation | N/A | q09 không có chunks, confidence 0.1, answer nói không đủ thông tin |

**Kết luận:** Deterministic synthesis fallback giúp chống hallucination tốt hơn cho câu thiếu evidence.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow

```text
Không có artifact Day 08 trong repo để đo lại.
Theo kiến trúc single-agent, khi answer sai phải đọc chung indexing/retrieval/generation.
```

### Day 09 — Debug workflow

```text
Khi answer sai -> mở trace JSON
  -> kiểm supervisor_route + route_reason
  -> kiểm retrieved_sources
  -> kiểm mcp_tools_used
  -> kiểm worker_io_logs
  -> sửa đúng worker liên quan
```

**Câu cụ thể nhóm đã debug:** q09 `ERR-403-AUTH`. Trace cho thấy route ban đầu qua `human_review`, sau đó retrieval trả rỗng. Vì synthesis thấy `retrieved_chunks=[]`, answer abstain và confidence 0.1. Nếu answer bị bịa, lỗi sẽ nằm ở synthesis fallback chứ không phải retrieval.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa pipeline/prompt chính | Thêm tool vào `mcp_server.py`, policy worker gọi qua `dispatch_tool()` |
| Thêm 1 domain mới | Dễ phình prompt | Thêm worker hoặc domain boosts trong retrieval |
| Thay đổi retrieval strategy | Sửa trực tiếp pipeline | Chỉ sửa `workers/retrieval.py` |
| A/B test một phần | Khó tách | Có thể swap worker riêng |

**Nhận xét:** Trong bài này, chuyển retrieval từ Chroma placeholder sang offline keyword chỉ cần sửa `workers/retrieval.py`; `graph.py` và synthesis không phải đổi contract.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|--------------|--------------|
| Simple query | N/A | 0 LLM calls, 0 MCP calls |
| Policy query | N/A | 0 LLM calls, 1-3 MCP calls |
| Complex access + P1 | N/A | 0 LLM calls, 3 MCP calls |

**Nhận xét về cost-benefit:** Đường chạy chính hiện dùng deterministic synthesis nên chi phí API bằng 0 và latency trung bình 1 ms. Đổi lại, hệ thống phụ thuộc vào rule/template; nếu câu hỏi tự do hơn thì nên bật LLM grounded hoặc dùng classifier tốt hơn.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**

1. Debug rõ hơn: trace cho biết route, worker sequence, source và MCP tools.
2. Dễ mở rộng: MCP tool và retrieval/synthesis có thể sửa độc lập.

**Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Với câu fact đơn giản như q01/q04, multi-agent không làm answer thông minh hơn; chỉ thêm trace và cấu trúc.

**Khi nào không nên dùng multi-agent?**

Không nên dùng khi KB rất nhỏ, câu hỏi chỉ là single-doc lookup, và không cần trace/tool/HITL. Khi đó retrieval + synthesis đơn giản đủ dùng.

**Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Thêm LLM classifier có fallback rule-based để route linh hoạt hơn, đồng thời giữ `route_reason` dạng structured: `matched_keywords`, `risk_flags`, `selected_route`.
