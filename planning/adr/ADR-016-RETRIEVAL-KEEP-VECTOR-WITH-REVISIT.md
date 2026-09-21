# ADR-016 — Retrieval chính vẫn là lexical, vector ở lại làm đường semantic

**Trạng thái:** đã chốt · 2026-09-21
**Liên quan:** ADR-003 §3.2 (embedding offline), guides §5.4 (rerank phải có số),
AI-PRODUCTION-PLAN P1.

## 1. Số đo (không phải ước lượng)

Đo ngày 2026-09-21 trên `eval/datasets/retrieval.jsonl` (16 query, corpus 16 mục
`content/kb/*.md`), top-4:

| | Recall@4 | MRR | Trễ/query | Giá/query | Mạng |
|---|---|---|---|---|---|
| Lexical (Python) | **1.00** | **1.00** (cả 16 đứng hạng 1) | **2ms** | 0 | không |
| Vector (Gemini embed + Pinecone) | 1.00 | 0.94 | ~3 000ms | >0 | có |

## 2. Vì sao KHÔNG bỏ Pinecone dù số thua

Tập eval thiên vị keyword — query do người viết, ngắn, đúng từ trong `keywords`
(điều này tự nhận trong `eval/guidelines/annotation.md` §3). Query thật của người
học không như vậy ("thang điểm" vs "quy đổi điểm số" là ví dụ mà lexical không
bao giờ khớp). Bỏ vector vì thắng trên tập thiên vị là tối ưu theo metric sai.

Đảo thứ tự (lexical trước, vector khi lexical rỗng) cũng KHÔNG làm hôm nay:
lexical trả *có gì đó* nhưng sai vẫn chặn mất đáp án vector đúng — phân biệt hai
trường hợp đó cần log query thật, mà log đó (P1.2, `kb_retrieval` theo
`request_id`) mới tồn tại từ hôm nay.

## 3. Chốt

- Giữ thứ tự hiện tại: vector trước, lexical fallback (đã chứng minh rơi êm).
- Không thêm reranker: chưa có số nào cho thấy retrieval thiếu (§5.4).
- Không đụng ADR-003 §3.2 hôm nay: Pinecone + Gemini vẫn là lựa chọn vận hành,
  và quyết định đó chờ số production, không chờ tập curated.

## 4. Điều kiện xem lại (ghi thành số, không thành cảm tính)

- 30 ngày log `kb_retrieval`: tỉ lệ query "không có mục nào khớp" >10%/tuần, hoặc
- corpus vượt 200 chunk, hoặc
- đo lại trên query THẬT (lấy từ log, gắn nhãn relevant_refs): lexical thua vector
  ≥5 điểm MRR.

Tới một trong ba thì làm thí nghiệm đảo thứ tự, với cùng bảng số §1 chạy lại.
