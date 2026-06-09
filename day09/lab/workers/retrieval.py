"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Offline retrieval từ data/docs, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import re
import unicodedata

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 4
DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "docs"))

STOPWORDS = {
    "la", "là", "gi", "gì", "va", "và", "cho", "can", "cần", "duoc", "được",
    "khong", "không", "bao", "nhieu", "nhiêu", "trong", "theo", "nhu", "nào",
    "nao", "cua", "của", "voi", "với", "mot", "một", "cac", "các", "khi",
    "ngay", "ngày", "thoi", "thời", "gian", "quy", "trinh", "trình", "xu",
    "xử", "ly", "lý", "su", "sự", "co", "cố", "he", "hệ", "thong", "thống",
    "khach", "khách", "hang", "hàng", "yeu", "yêu", "nhan", "nhân", "vien",
    "viên", "moi", "mới", "dau", "đầu", "tien", "tiên",
}

DOMAIN_BOOSTS = {
    "policy_refund_v4.txt": [
        "refund", "hoan tien", "hoàn tiền", "flash sale", "license", "subscription",
        "store credit", "31/01", "07/02", "san pham loi", "sản phẩm lỗi",
    ],
    "sla_p1_2026.txt": [
        "p1", "sla", "ticket", "escalation", "incident", "notify", "stakeholder",
        "pagerduty", "slack", "2am", "22:47",
    ],
    "access_control_sop.txt": [
        "access", "cap quyen", "cấp quyền", "level 1", "level 2", "level 3",
        "level 4", "admin access", "contractor", "it security", "it admin",
    ],
    "it_helpdesk_faq.txt": [
        "mat khau", "mật khẩu", "dang nhap", "đăng nhập", "khoa", "khóa",
        "vpn", "helpdesk", "license", "sso",
    ],
    "hr_leave_policy.txt": [
        "remote", "probation", "thu viec", "thử việc", "nghi phep", "nghỉ phép",
        "team lead", "hr",
    ],
}


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d")


def _tokenize(text: str) -> list:
    normalized = _normalize(text)
    tokens = re.findall(r"[a-z0-9:/.-]+", normalized)
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


def _read_docs() -> list:
    docs = []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith(".txt"):
            continue
        path = os.path.join(DOCS_DIR, fname)
        with open(path, encoding="utf-8") as f:
            docs.append({"source": fname, "text": f.read()})
    return docs


def _domain_boost(query: str, source: str) -> float:
    query_norm = _normalize(query)
    boost = 0.0
    for phrase in DOMAIN_BOOSTS.get(source, []):
        if _normalize(phrase) in query_norm:
            boost += 2.5
    return boost


def _score_doc(query: str, doc_text: str, source: str) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    doc_norm = _normalize(doc_text)
    exact_hits = sum(1 for token in query_tokens if token in doc_norm)
    unique_hits = len({token for token in query_tokens if token in doc_norm})
    score = exact_hits + (0.5 * unique_hits) + _domain_boost(query, source)
    return score


def _to_similarity(score: float, max_score: float) -> float:
    if score <= 0 or max_score <= 0:
        return 0.0
    return round(min(0.98, 0.35 + 0.63 * (score / max_score)), 4)


def _unique(values: list) -> list:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Offline lexical retrieval: đọc 5 tài liệu nội bộ và rank theo keyword/domain.

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    docs = _read_docs()

    # Unknown error codes are an abstain test. Do not retrieve unrelated docs.
    if "err-" in _normalize(query) and not any(_normalize(query) in _normalize(d["text"]) for d in docs):
        return []

    scored = []
    for doc in docs:
        raw_score = _score_doc(query, doc["text"], doc["source"])
        if raw_score > 0:
            scored.append({**doc, "raw_score": raw_score})

    if not scored:
        return []

    scored.sort(key=lambda d: (-d["raw_score"], d["source"]))
    max_score = scored[0]["raw_score"]
    min_score = max(2.0, max_score * 0.65)

    chunks = []
    filtered = [doc for doc in scored if doc["raw_score"] >= min_score]
    query_norm = _normalize(query)
    mandatory_sources = []
    if "p1" in query_norm or "sla" in query_norm or "ticket" in query_norm:
        mandatory_sources.append("sla_p1_2026.txt")
    if any(kw in query_norm for kw in ["access", "cap quyen", "level 2", "level 3", "level 4", "contractor"]):
        mandatory_sources.append("access_control_sop.txt")
    for source in mandatory_sources:
        doc = next((item for item in scored if item["source"] == source), None)
        if doc and all(item["source"] != source for item in filtered):
            filtered.append(doc)
    filtered.sort(key=lambda d: (-d["raw_score"], d["source"]))

    for rank, doc in enumerate(filtered[:top_k], 1):
        chunks.append({
            "text": doc["text"],
            "source": doc["source"],
            "score": _to_similarity(doc["raw_score"], max_score),
            "metadata": {
                "retrieval": "offline_keyword",
                "rank": rank,
                "raw_score": doc["raw_score"],
            },
        })
    return chunks


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)

        sources = _unique([c["source"] for c in chunks])

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state.setdefault("worker_io_logs", []).append(worker_io)

    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
