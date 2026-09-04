"""Cổng dạng của phần giải thích được backfill.

`check_shape` là thứ duy nhất đứng giữa đầu ra của model và cột
`question.explanation`, mà cột ấy đi thẳng ra màn hình người học. Nên luật của
nó được ghim ở đây, và không bài nào cần mạng.

Luật đáng ngờ nhất — và là luật dễ bị gỡ nhất vì trông như khó tính vô cớ — là
**đoạn căn cứ không được nhắc chữ cái nào**. Lý do nằm ở `part7_system.md`: lời
giải được viết TRƯỚC khi các phương án bị xáo lại, nên một chữ cái nằm ngoài đoạn
của chính nó sẽ trỏ sang một phương án khác sau khi xáo. Ở đường backfill này
phương án không bị xáo, nhưng luật vẫn giữ để hai đường sinh ra cùng một hình
dạng — nếu không, hai nửa của cùng một đề đọc ra hai kiểu.
"""

from app.content.backfill_explanations import check_shape

ABCD = ["A", "B", "C", "D"]
ABC = ["A", "B", "C"]

GOOD = (
    'Câu hỏi hỏi về thời điểm, và đoạn văn viết "The shipment arrives on Tuesday". | '
    '(A) "Monday" trái với ngày nêu trong đoạn văn. | '
    '(B) "Tuesday" khớp đúng câu vừa trích. | '
    '(C) "Wednesday" có được nhắc nhưng là ngày họp, sai chi tiết. | '
    '(D) "Thursday" không xuất hiện ở đâu trong đoạn văn.'
)


def test_a_well_formed_line_passes():
    assert check_shape(GOOD, ABCD) is None


def test_a_missing_segment_is_counted_not_judged():
    """Ba phương án sai thì ba đoạn. Thiếu một đoạn là đếm ra được.

    Đây chính là thứ khiến câu "các phương án còn lại đều không phù hợp" không
    viết ra được — nó là một đoạn, không phải bốn.
    """
    short = GOOD.rsplit(" | ", 1)[0]
    problem = check_shape(short, ABCD)
    assert problem is not None and "4 đoạn" in problem and "5" in problem


def test_a_letter_in_the_evidence_segment_is_refused():
    bad = GOOD.replace("Câu hỏi hỏi về thời điểm", "Đáp án (B) đúng vì hỏi về thời điểm", 1)
    problem = check_shape(bad, ABCD)
    assert problem is not None and "(B)" in problem


def test_segments_must_open_with_their_own_letter():
    """Đổi chỗ hai đoạn thì dòng vẫn trôi chảy, vẫn đủ số đoạn, và vẫn sai.

    Không có phép kiểm này thì đoạn mô tả (A) nằm ở chỗ của (B) sẽ vào thẳng
    database — người học đọc một lời giải đúng ngữ pháp, đúng giọng, và trỏ
    nhầm phương án.
    """
    parts = GOOD.split(" | ")
    parts[1], parts[2] = parts[2], parts[1]
    problem = check_shape(" | ".join(parts), ABCD)
    assert problem is not None and "(A)" in problem


def test_a_line_break_is_refused():
    """`Explanation:` được đọc như MỘT trường; xuống dòng cắt mất phần sau."""
    assert check_shape(GOOD.replace(" | (C)", "\n| (C)", 1), ABCD) is not None


def test_three_option_parts_are_measured_against_three():
    """Part 2 có ba phương án, không phải bốn — số đoạn đếm theo câu hỏi thật."""
    three = " | ".join(GOOD.split(" | ")[:4])
    assert check_shape(three, ABC) is None
    assert check_shape(three, ABCD) is not None


def test_empty_output_is_refused():
    assert check_shape("   ", ABCD) is not None


def test_a_missing_scene_file_yields_no_description(tmp_path, monkeypatch):
    """Không có bản mô tả cảnh thì `scene_for` trả `None`, và `None` nghĩa là BỎ QUA.

    Đây là chốt duy nhất giữ Part 1 khỏi bịa. Model không nhìn được bức ảnh, còn
    ảnh Part 1 thì cố ý không có `alt_text` (ADR-004) — nên nếu chỗ này trả về
    một chuỗi rỗng thay vì `None`, lời giải vẫn được viết, vẫn đọc trôi chảy, và
    mô tả một bức ảnh chưa ai từng thấy.
    """
    from app.content import backfill_explanations as mod

    monkeypatch.setattr(mod, "blueprint_path", lambda slug: tmp_path / "khong-co.json")
    assert mod.scene_for("tp-form-06", 1) is None


def test_a_scene_is_read_through_the_blueprint_not_a_guessed_filename(tmp_path, monkeypatch):
    """Tên tệp lấy từ `blueprint.json`, không dựng bằng `f"p1-{number:02d}"`.

    Quy ước đặt tên là chuyện của đường sinh đề. Đoán nó ở đây nghĩa là hai nơi
    phải cùng đổi khi nó đổi, và nơi này sẽ không ai nhớ — hỏng ra thành "Part 1
    tự nhiên bị bỏ qua hết", một triệu chứng không trỏ về nguyên nhân.
    """
    import json

    from app.content import backfill_explanations as mod

    blueprint = tmp_path / "blueprint.json"
    blueprint.write_text(
        json.dumps({"parts": [{"part": 1, "slots": [{"number": 3, "id": "canh-dac-biet"}]}]})
    )
    photos = tmp_path / mod.PHOTO_DIR
    photos.mkdir()
    (photos / "canh-dac-biet.txt").write_text("A photograph of one man at a desk.\n")

    monkeypatch.setattr(mod, "blueprint_path", lambda slug: blueprint)
    monkeypatch.setattr(mod, "workdir_for", lambda slug: tmp_path)

    assert mod.scene_for("tp-form-06", 3) == "A photograph of one man at a desk."
    # Số không có trong blueprint thì không có cảnh, chứ không phải đoán bừa.
    assert mod.scene_for("tp-form-06", 4) is None
