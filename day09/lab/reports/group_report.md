# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Ngũ Hổ Tướng  
**Thành viên:**

| Tên | Vai trò | Email |
| ---- | ------------------ | ----- |
| Hoàng Văn Anh | Supervisor + Worker + MCP + Trace/Docs Owner | N/A |

**Ngày nộp:** 09/06/2026  
**Repo:** `day09/lab`

---

## 1. Kiến trúc nhóm đã xây dựng

Nhóm xây dựng hệ Supervisor-Worker trong `graph.py`. Supervisor chỉ quyết định luồng, không trả lời domain knowledge. Ba worker chính là `retrieval_worker`, `policy_tool_worker`, và `synthesis_worker`. Sau khi sửa, `graph.py` đã bỏ placeholder và gọi trực tiếp các worker thật qua `retrieval_run`, `policy_tool_run`, `synthesis_run`.

Routing logic cốt lõi dùng rule-based keyword matching để dễ debug: câu factual SLA/IT/HR đi `retrieval_worker`; câu policy exception, refund decision, access control hoặc temporal scoping đi `policy_tool_worker`; câu lỗi không rõ như `ERR-*` trigger HITL placeholder rồi retrieval để kiểm evidence. Mỗi route ghi `route_reason` rõ ràng vào trace.

MCP tools đã tích hợp:

- `search_kb`: policy worker dùng để lấy evidence qua MCP.
- `check_access_permission`: kiểm Level 2/3/4 access, approvers, emergency override.
- `get_ticket_info`: lấy mock P1 ticket, notifications và SLA deadline.
- `create_ticket`: tool mock mở rộng, chưa dùng trong 15 câu test.

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Dùng retrieval offline + deterministic synthesis làm đường chạy chính.

**Bối cảnh vấn đề:** Skeleton ban đầu có ChromaDB/LLM, nhưng collection trong môi trường hiện tại rỗng và `graph.py` vẫn trả placeholder. Nếu phụ thuộc embedding model hoặc API key, pipeline có thể chạy không ổn định khi chấm. Mục tiêu lab là trace rõ, source đúng, không hallucinate.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
| ------------ | ---------- | -------------- |
| ChromaDB + LLM | Gần RAG production hơn | Cần index/model/API; dễ fail môi trường |
| Keyword retrieval + deterministic synthesis | Chạy offline, ổn định, trace dễ kiểm | Kém linh hoạt nếu câu hỏi ngoài template lab |

**Phương án đã chọn và lý do:** Chọn offline deterministic path. Retrieval đọc trực tiếp 5 file `data/docs/*.txt`, score theo keyword/domain boost và threshold để source sạch. Synthesis chỉ dùng `retrieved_chunks` + `policy_result`, có rule abstain nếu không có evidence.

**Bằng chứng từ trace/code:**

```text
Batch eval_20260609_114716_162914:
- 15/15 câu chạy thành công
- route_match: 15/15
- source_coverage: 15/15
- avg_confidence: 0.871
- mcp_usage_rate: 6/15
- q09 ERR-403-AUTH: retrieved_sources=[], confidence=0.1, answer abstain
```

---

## 3. Kết quả test questions

**Tổng điểm nội bộ ước tính trên `test_questions.json`:** route/source đạt 15/15. Đây không phải grading hidden score, nhưng là bằng chứng pipeline xử lý đúng public tests.

**Câu pipeline xử lý tốt nhất:**

- ID: q15 — Đây là câu multi-hop P1 + Level 2 access. Trace `run_20260609_114716_187197_ef1d5a.json` route `policy_tool_worker`, gọi đủ `search_kb`, `check_access_permission`, `get_ticket_info`, và retrieved sources gồm `sla_p1_2026.txt`, `access_control_sop.txt`.

**Câu pipeline fail hoặc partial:**

- Không có câu public test fail về route/source sau batch cuối. Rủi ro còn lại là một số câu hidden có phrasing khác rule hiện tại.

**Câu q09 (abstain):** Hệ thống trigger HITL placeholder, retrieval trả rỗng, synthesis trả “Không đủ thông tin trong tài liệu nội bộ...”, confidence `0.1`. Đây là hành vi mong muốn để tránh hallucination.

**Câu q15 multi-hop:** Trace ghi `policy_tool_worker -> retrieval_worker -> synthesis_worker`, MCP có 3 calls và answer nêu đủ P1 notify/escalation + Level 2 emergency access.

---

## 4. So sánh Day 08 vs Day 09

Không có artifact Day 08 trong repo để đo baseline thực tế, nên nhóm không bịa số liệu. Với Day 09, metric rõ nhất là observability: mỗi trace có `supervisor_route`, `route_reason`, `workers_called`, `retrieved_sources`, `mcp_tools_used`, `confidence`.

Metric thay đổi rõ nhất trong lab hiện tại là khả năng debug. Khi q09 không có thông tin, trace chỉ ra đúng chuỗi: `human_review -> retrieval_worker -> synthesis_worker`, source rỗng và confidence thấp. Với single-agent, phải đọc toàn pipeline để đoán lỗi nằm ở retrieve hay generate.

Trường hợp multi-agent không giúp nhiều là câu đơn giản như q01 hoặc q04. Những câu đó retrieval + synthesis là đủ; supervisor-worker chủ yếu thêm trace.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
| ------------ | ------------------- | ------ |
| Hoàng Văn Anh | `graph.py`, workers, MCP integration, eval trace, docs/report | 1-4 |

**Điều nhóm làm tốt:** Ưu tiên đường chạy thật thay vì giữ skeleton. Sau sửa, output không còn `[PLACEHOLDER]`, trace không bị ghi đè vì `run_id` đã có microsecond + uuid, và policy routes có MCP calls thực tế.

**Điều nhóm làm chưa tốt:** Chưa có Day 08 baseline để so sánh số liệu đầy đủ. Synthesis deterministic còn phụ thuộc rule nên cần cải thiện nếu câu hỏi hidden viết khác nhiều.

**Nếu làm lại:** Nhóm sẽ viết test nhỏ ngay từ đầu cho route/source match, thay vì phát hiện muộn rằng `graph.py` vẫn gọi placeholder.

---

## 6. Nếu có thêm 1 ngày

Nhóm sẽ thêm một lớp LLM classifier có fallback rule-based cho supervisor. Lý do: batch public đã đúng 15/15, nhưng route hiện vẫn phụ thuộc keyword. Classifier có thể giúp câu hidden paraphrase tốt hơn, còn fallback giữ ổn định khi API lỗi.
