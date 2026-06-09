# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hoàng Văn Anh - 2A202600762  
**Vai trò trong nhóm:** Supervisor Owner / Worker Owner / MCP Owner / Trace & Docs Owner  
**Ngày nộp:** 09/06/2026

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách hoàn thiện đường chạy chính của lab từ skeleton thành pipeline chạy thật. File chính tôi sửa là `graph.py`, `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`, `mcp_server.py`, `eval_trace.py` và các file docs/report. Trong `graph.py`, tôi nối graph với worker thật bằng `retrieval_run`, `policy_tool_run`, `synthesis_run`, thay cho placeholder cũ. Trong `workers/retrieval.py`, tôi chuyển retrieval sang offline keyword search trên `data/docs/*.txt`. Trong `workers/policy_tool.py`, tôi đảm bảo policy route gọi MCP tools thật: `search_kb`, `check_access_permission`, `get_ticket_info`. Trong `workers/synthesis.py`, tôi làm fallback deterministic để trả lời có citation và abstain khi thiếu evidence. Bằng chứng là batch trace `eval_20260609_114716_162914` chạy đủ 15/15 câu, route/source match 15/15.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tôi chọn retrieval offline + deterministic synthesis làm đường chạy chính, thay vì phụ thuộc ChromaDB index và LLM API.

Lý do là môi trường lab cần chạy chắc. Khi đọc repo, tôi thấy `graph.py` vẫn trả `[PLACEHOLDER]`, Chroma collection rỗng, còn synthesis cũ nếu không gọi được OpenAI/Gemini sẽ trả `[SYNTHESIS ERROR]`. Nếu nộp trạng thái đó, trace có thể tồn tại nhưng answer không đạt. Tôi cân nhắc hai hướng: giữ Chroma/LLM để giống production hơn, hoặc dùng offline deterministic path để bảo đảm kết quả. Tôi chọn hướng thứ hai vì KB chỉ có 5 tài liệu và câu hỏi lab có domain rõ.

Trade-off tôi chấp nhận là hệ thống kém linh hoạt hơn với câu hỏi paraphrase lạ. Đổi lại, pipeline chạy không cần network/API, source sạch và chống hallucination tốt. Bằng chứng: q09 `ERR-403-AUTH` có `retrieved_sources=[]`, confidence `0.1`, answer nói không đủ thông tin. q15 multi-hop gọi đủ MCP tools và trả cả SLA P1 + Level 2 emergency access.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `graph.py` vẫn dùng placeholder worker và trace bị ghi đè do `run_id` chỉ chính xác tới giây.

**Symptom:** Trước khi sửa, chạy `python eval_trace.py` báo 15/15 succeeded nhưng trong `artifacts/traces` chỉ còn vài file vì nhiều câu chạy cùng giây dùng chung `run_id`. Answer cũng là `[PLACEHOLDER] Câu trả lời được tổng hợp từ 1 chunks.`, source gần như luôn là `sla_p1_2026.txt`, MCP usage là 0%.

**Root cause:** Trong `graph.py`, các import worker thật bị comment, các node `retrieval_worker_node`, `policy_tool_worker_node`, `synthesis_worker_node` tự tạo output giả. `make_initial_state()` dùng `datetime.now().strftime('%Y%m%d_%H%M%S')`, nên trace file bị overwrite.

**Cách sửa:** Tôi import worker thật, thay wrapper bằng `return retrieval_run(state)`, `return policy_tool_run(state)`, `return synthesis_run(state)`. Tôi đổi `run_id` sang format có microsecond và uuid ngắn. Sau sửa, batch `eval_20260609_114716_162914` có đủ 15 trace riêng, `mcp_usage_rate=6/15`, `avg_confidence=0.871`, `hitl_rate=1/15`.

---

## 4. Tôi tự đánh giá đóng góp của mình

Tôi làm tốt nhất ở phần biến skeleton thành hệ thống chạy thật và có bằng chứng trace. Tôi cũng cố giữ giải pháp dễ giải thích: supervisor rule-based, retrieval offline, policy worker gọi MCP, synthesis không bịa. Điểm còn yếu là giải pháp hiện chưa phải RAG production thật; retrieval keyword phù hợp lab nhỏ nhưng nếu KB lớn thì cần vector index hoặc hybrid search. Nhóm phụ thuộc vào tôi ở phần orchestration và trace: nếu graph vẫn placeholder thì các docs/report dù viết hay cũng không có giá trị. Tôi phụ thuộc vào dữ liệu đề bài và expected answers; riêng access policy có chỗ hơi lệch giữa tài liệu và câu test nên tôi phải xử lý theo `Level` được hỏi.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm test tự động cho 15 public questions: kiểm `supervisor_route`, expected source coverage, không có `[PLACEHOLDER]`, và policy route phải có MCP call. Lý do là lỗi lớn nhất ban đầu không phải syntax mà là pipeline “chạy được nhưng chạy giả”; test này sẽ bắt lỗi đó ngay.
