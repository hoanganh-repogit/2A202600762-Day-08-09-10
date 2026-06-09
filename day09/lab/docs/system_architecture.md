# System Architecture — Lab Day 09

**Nhóm:** Ngũ Hổ Tướng  
**Ngày:** 09/06/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

**Pattern đã chọn:** Supervisor-Worker.

Hệ thống hiện tại là orchestration graph Python thuần trong `graph.py`. Supervisor không tự trả lời domain knowledge; supervisor chỉ đọc câu hỏi, gắn `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`, sau đó chuyển state sang worker phù hợp. Worker giữ domain skill:

- `retrieval_worker`: tìm evidence offline từ `data/docs/*.txt`.
- `policy_tool_worker`: xử lý policy/exception và gọi MCP tools.
- `synthesis_worker`: tổng hợp câu trả lời có citation và abstain khi thiếu evidence.
- `human_review`: placeholder HITL cho câu rủi ro như mã lỗi không rõ.

Lý do chọn pattern này thay vì single agent: trace cho biết lỗi nằm ở routing, retrieval, policy/MCP hay synthesis. Trong batch `eval_20260609_114716_162914`, hệ thống chạy 15/15 câu không crash, route match expected 15/15 và source coverage 15/15.

---

## 2. Sơ đồ Pipeline

```text
User question
     |
     v
Supervisor in graph.py
  - route_reason
  - risk_high
  - needs_tool
     |
     +--> retrieval_worker ----------------+
     |    offline evidence from data/docs  |
     |                                      v
     +--> policy_tool_worker ----------> retrieval_worker
     |    MCP: search_kb,                 extra evidence for synthesis
     |         check_access_permission,
     |         get_ticket_info
     |
     +--> human_review placeholder ----> retrieval_worker
                                            |
                                            v
                                  synthesis_worker
                                  grounded answer + sources
                                            |
                                            v
                                          trace JSON
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Chọn route, set risk/tool flags, không tự trả lời kiến thức nội bộ |
| **Input** | `task` |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Rule-based keyword routing: SLA/IT/HR fact → retrieval; access/refund exception/temporal/store credit → policy; ERR/risk → HITL rồi retrieval |
| **HITL condition** | `ERR-*` hoặc risk keyword không đủ context |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Trả về evidence chunks và source files |
| **Retrieval strategy** | Offline lexical/domain scoring trên 5 file `data/docs/*.txt` |
| **Top-k** | Default 4, có threshold để loại source nhiễu |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích policy/exception và ghi MCP calls vào state |
| **MCP tools gọi** | `search_kb`, `check_access_permission`, `get_ticket_info` |
| **Exception cases xử lý** | Flash Sale, digital product/license, activated product, temporal scoping trước 01/02/2026, access emergency bypass |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | Không bắt buộc trong đường chạy chính; có `USE_LLM_SYNTHESIS=1` nếu muốn thử |
| **Fallback chính** | Deterministic grounded synthesis |
| **Grounding strategy** | Chỉ trả lời theo `retrieved_chunks` và `policy_result` |
| **Abstain condition** | Không có chunks, mã lỗi không tồn tại, hoặc hỏi thông tin không có trong docs |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| `search_kb` | `query`, `top_k` | `chunks`, `sources`, `total_found` |
| `get_ticket_info` | `ticket_id` | ticket details, SLA deadline, notifications |
| `check_access_permission` | `access_level`, `requester_role`, `is_emergency` | `can_grant`, approvers, emergency override |
| `create_ticket` | `priority`, `title`, `description` | mock ticket id, URL, created_at |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| `task` | str | Câu hỏi đầu vào | supervisor đọc |
| `supervisor_route` | str | Worker được chọn | supervisor ghi |
| `route_reason` | str | Lý do route | supervisor ghi, trace đọc |
| `risk_high` | bool | Cờ rủi ro/HITL | supervisor ghi |
| `needs_tool` | bool | Cờ cho phép MCP | supervisor ghi, policy đọc |
| `retrieved_chunks` | list | Evidence từ docs | retrieval/policy ghi, synthesis đọc |
| `retrieved_sources` | list | Source files | retrieval/policy ghi, trace đọc |
| `policy_result` | dict | Kết quả policy/MCP | policy ghi, synthesis đọc |
| `mcp_tools_used` | list | Tool calls đầy đủ | policy ghi |
| `final_answer` | str | Câu trả lời cuối | synthesis ghi |
| `confidence` | float | Mức tin cậy 0-1 | synthesis ghi |
| `worker_io_logs` | list | Input/output từng worker | workers ghi |
| `run_id` | str | ID trace unique | graph ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|-----------------------------|
| Debug khi sai | Khó biết lỗi ở retrieve, policy hay answer | Trace tách `route_reason`, `workers_called`, `worker_io_logs` |
| Thêm capability mới | Sửa prompt/pipeline chính | Thêm MCP tool hoặc worker riêng |
| Routing visibility | Không có route rõ | Có `supervisor_route` và `route_reason` |
| Abstain | Dễ bị LLM đoán | Synthesis fallback trả "Không đủ thông tin" khi thiếu chunks |

Quan sát thực tế: q09 `ERR-403-AUTH` có `retrieved_sources=[]`, confidence `0.1`, `hitl_triggered=True` và answer abstain; không bịa mã lỗi.

---

## 6. Giới hạn và điểm cần cải tiến

1. Retrieval offline rất ổn cho 5 tài liệu nhỏ nhưng chưa phù hợp KB lớn.
2. Synthesis deterministic chính xác cho câu lab, nhưng chưa linh hoạt bằng LLM grounded khi câu hỏi đa dạng hơn.
3. Access SOP có điểm hơi lệch giữa tài liệu và expected test: tài liệu gọi Level 3 là Elevated Access, còn một câu test viết "Admin Access (Level 3)". Hệ thống ưu tiên `Level 3` khi câu hỏi ghi rõ level.
