# Routing Decisions Log — Lab Day 09

**Nhóm:** Ngũ Hổ Tướng  
**Ngày:** 09/06/2026  
**Trace batch:** `eval_20260609_114716_162914`

> Nguồn số liệu: các trace JSON trong `artifacts/traces/` có `eval_batch_id=eval_20260609_114716_162914`.

---

## Routing Decision #1 — SLA fact lookup

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Trace file:** `run_20260609_114716_162933_00f9fd.json`  
**Route reason:** `task contains factual SLA/IT/HR keyword; retrieval worker selected`  
**MCP tools được gọi:** none  
**Workers called sequence:** `retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer: Ticket P1 phản hồi ban đầu 15 phút, resolution 4 giờ.
- sources: `sla_p1_2026.txt`
- confidence: `0.95`
- Correct routing? Yes

**Nhận xét:** Đây là câu factual single-doc nên không cần MCP/policy. Retrieval offline trả đúng một source, synthesis cite đúng.

---

## Routing Decision #2 — Refund exception

**Task đầu vào:**
> Sản phẩm kỹ thuật số (license key) có được hoàn tiền không?

**Worker được chọn:** `policy_tool_worker`  
**Trace file:** `run_20260609_114716_171509_e79ddf.json`  
**Route reason:** `task asks for policy decision/exception; policy worker must call MCP tools`  
**MCP tools được gọi:** `search_kb`  
**Workers called sequence:** `policy_tool_worker -> retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer: Không được hoàn tiền vì license key/subscription là digital product exception.
- sources: `policy_refund_v4.txt`
- confidence: `0.88`
- Correct routing? Yes

**Nhận xét:** Câu này không chỉ hỏi fact mà hỏi policy exception. Policy worker phát hiện `digital_product_exception`, MCP `search_kb` ghi vào trace, retrieval chạy sau để cung cấp source sạch cho synthesis.

---

## Routing Decision #3 — Multi-hop P1 + Access

**Task đầu vào:**
> Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để thực hiện emergency fix. Đồng thời cần notify stakeholders theo SLA. Nêu đủ cả hai quy trình.

**Worker được chọn:** `policy_tool_worker`  
**Trace file:** `run_20260609_114716_187197_ef1d5a.json`  
**Route reason:** `task contains access-control keyword; policy worker must call MCP tools | risk_high flagged`  
**MCP tools được gọi:** `search_kb`, `check_access_permission`, `get_ticket_info`  
**Workers called sequence:** `policy_tool_worker -> retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer: Trả lời hai quy trình song song: P1 notify/escalation và Level 2 emergency access.
- sources: `sla_p1_2026.txt`, `access_control_sop.txt`
- confidence: `0.95`
- Correct routing? Yes

**Nhận xét:** Đây là route khó nhất vì cần cả SLA P1 và access policy. Policy worker dùng MCP để lấy permission/ticket context, retrieval worker đảm bảo synthesis có cả hai nguồn.

---

## Routing Decision #4 — HITL/abstain

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn ban đầu:** `human_review`, sau đó auto-approved về `retrieval_worker`  
**Trace file:** `run_20260609_114716_175089_55972a.json`  
**Route reason cuối:** `unknown error code + risk_high -> human review | human approved -> retrieval`  
**MCP tools được gọi:** none  
**Workers called sequence:** `human_review -> retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer: Không đủ thông tin trong tài liệu nội bộ để xác định mã lỗi này; chuyển IT Helpdesk/human review.
- sources: none
- confidence: `0.1`
- Correct routing? Yes

**Nhận xét:** Đây là test anti-hallucination. Retrieval trả `retrieved_chunks=[]`, synthesis abstain rõ ràng, không bịa ý nghĩa mã lỗi.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| `retrieval_worker` | 9 | 60% |
| `policy_tool_worker` | 6 | 40% |
| `human_review` | 1 triggered trong sequence | 6% HITL rate |

### Routing Accuracy

- Câu route đúng theo `test_questions.json`: 15 / 15
- Source coverage theo expected sources: 15 / 15
- Câu trigger HITL: 1 (`q09`)
- MCP usage: 6 / 15 câu

### Lesson Learned về Routing

1. Keyword routing đủ tốt cho lab nhỏ nếu `route_reason` cụ thể và có rule riêng cho simple fact vs policy decision.
2. Multi-hop access + P1 nên route policy trước để gọi MCP, rồi vẫn chạy retrieval worker để source cuối sạch và dễ cite.

### Route Reason Quality

`route_reason` hiện đủ để debug vì nó ghi rõ vì sao chọn route: factual lookup, policy decision, access-control keyword, risk flag, hoặc unknown error. Cải tiến tiếp theo là thêm matched keywords cụ thể vào trace, ví dụ `matched_keywords=["level 2", "p1", "2am"]`.
