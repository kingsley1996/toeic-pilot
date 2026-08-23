"""Sinh đề: blueprint, cổng kiểm, và thứ tự ghép khi nạp.

Không bài nào gọi mô hình. Thứ đáng kiểm ở đây là **cái cổng**, không phải chất
lượng văn bản mô hình viết ra — chất lượng là việc của người duyệt, và một bài
test giả vờ đo được nó sẽ chỉ đo được chính prompt của nó.

Ba thứ được ghim, và cả ba đều hỏng im lặng:

  · blueprint mang mã nhãn không thuộc part — chỉ lộ ra sau khi đã sinh xong 30
    câu, và lúc đó thứ phải sửa là 30 tệp chứ không phải một dòng JSON;
  · một khối sai định dạng lọt qua cổng và đi tới database;
  · các tệp dán bị ghép sai thứ tự, làm câu 101 mang nội dung của ô khác — cả
    hai đều là câu Part 5 hợp lệ, nên không có gì báo.
"""

from pathlib import Path

from app.content.exam import blueprint as bp
from app.content.exam import check as checker
from app.content.exam import loader, writer
from app.services.llm.router import Tier

GOOD = """[QUESTION]
Regional managers must submit their expense reports ------- the fifteenth of each month.
(A) by
(B) until
(C) since
(D) among
Answer: A
Explanation: "by + mốc thời gian" là hạn chót.
Source: original
"""


def _plan(tmp_path: Path, count: int = 3) -> bp.Blueprint:
    plan = bp.build_part5("tp-test", "Đề kiểm thử", seed=7, count=count)
    bp.save(plan, tmp_path / "blueprint.json")
    return plan


def test_blueprint_uses_labels_that_exist_for_the_part(tmp_path):
    """Mã nhãn kiểm ngay ở blueprint, trước khi tốn một lượt gọi nào."""
    plan = _plan(tmp_path, count=30)
    assert plan.slot_count() == 30
    assert bp.validate(plan) == []
    # Số câu chuẩn của Part 5 là 101–130, và nó được LƯU chứ không suy ra lúc nạp.
    numbers = [slot.number for slot in plan.parts[0].slots]
    assert numbers == list(range(101, 131))

    plan.parts[0].slots[0].grammar = "GRAMMAR_TO_INFINITIVE"  # có thật, nhưng của Part 6
    problems = bp.validate(plan)
    assert len(problems) == 1
    assert "GRAMMAR_TO_INFINITIVE" in problems[0]


def test_the_same_seed_gives_the_same_layout(tmp_path):
    """`seed` làm BỐ CỤC lặp lại được — không phải câu chữ.

    Cái nó mua về: hai người chạy cùng một blueprint thì đang nói về cùng một đề,
    nên so sánh kết quả với nhau có nghĩa.
    """
    first = bp.build_part5("a", "A", seed=42)
    second = bp.build_part5("b", "B", seed=42)
    assert [slot.grammar for slot in first.parts[0].slots] == [
        slot.grammar for slot in second.parts[0].slots
    ]
    other = bp.build_part5("c", "C", seed=43)
    assert [slot.grammar for slot in other.parts[0].slots] != [
        slot.grammar for slot in first.parts[0].slots
    ]


def test_a_well_formed_block_passes_the_gate_it_will_meet_at_commit(tmp_path):
    """Cổng ở đây gọi ĐÚNG parser mà `POST /parts/parse` gọi.

    Viết một bản kiểm riêng thì nó sẽ trôi khỏi parser, và ngày nó trôi thì
    pipeline báo "hợp lệ" cho thứ máy chủ sẽ từ chối — hai câu trả lời trái ngược
    từ hai chỗ, không chỗ nào sai rõ ràng.
    """
    plan = _plan(tmp_path, count=1)
    writer.save_slot(tmp_path, plan.parts[0].slots[0], GOOD)

    reports = checker.check_blueprint(plan, tmp_path)
    assert [r.problems for r in reports] == [[]]
    assert not reports[0].blocked


def test_the_gate_blocks_what_a_weak_model_actually_produced(tmp_path):
    """Bốn kiểu hỏng dưới đây là bản ghi THẬT của một lượt chạy llama3.2 3B.

    Giữ nguyên chúng làm bài test thay vì bịa ra lỗi giả: đây là những gì mô hình
    nhỏ thật sự làm — viết bằng tiếng Việt, quên mốc `[QUESTION]`, dùng gạch dưới
    thay vì bảy gạch ngang, và ghi `Answer: (A) recruitment specialist` thay vì
    một chữ cái.
    """
    plan = _plan(tmp_path, count=1)
    slot = plan.parts[0].slots[0]

    writer.save_slot(
        tmp_path, slot, 'Dưới đây là câu hỏi:\n"Có ------- quan trọng?"\n(A) một\n(B) hai'
    )
    assert checker.check_blueprint(plan, tmp_path)[0].blocked

    writer.save_slot(tmp_path, slot, GOOD.replace("-------", "_________"))
    report = checker.check_blueprint(plan, tmp_path)[0]
    assert any("chỗ trống" in problem for problem in report.problems)

    writer.save_slot(tmp_path, slot, GOOD.replace("Source: original", "Source: licensed"))
    report = checker.check_blueprint(plan, tmp_path)[0]
    assert any("original" in problem for problem in report.problems)


def test_duplicate_prompts_inside_one_form_are_blocked(tmp_path):
    """Mô hình lặp lại chính nó nhiều hơn người ta tưởng.

    Hai câu giống nhau trong một đề là thứ người học nhận ra ngay còn máy thì
    không — nên phép so sánh phải nằm ở tầng đề, không ở tầng câu.
    """
    plan = _plan(tmp_path, count=2)
    for slot in plan.parts[0].slots:
        writer.save_slot(tmp_path, slot, GOOD)

    reports = checker.check_blueprint(plan, tmp_path)
    assert not reports[0].blocked
    assert any("trùng" in problem for problem in reports[1].problems)


def test_a_length_tell_is_a_flag_not_a_block(tmp_path):
    """Lựa chọn dài bất thường là chỗ NGƯỜI cần nhìn, không phải lỗi chặn nạp.

    Trộn hai loại lại thì người chạy học cách bỏ qua mã thoát, và lúc đó cả hai
    loại cùng mất tác dụng.
    """
    plan = _plan(tmp_path, count=1)
    writer.save_slot(
        tmp_path,
        plan.parts[0].slots[0],
        GOOD.replace("(A) by", "(A) by the end of the following business quarter"),
    )
    report = checker.check_blueprint(plan, tmp_path)[0]
    assert not report.blocked
    assert any("dài bất thường" in flag for flag in report.flags)


def test_paste_files_are_joined_in_question_number_order(tmp_path):
    """`commit_part` cấp số câu theo THỨ TỰ cụm trong danh sách.

    Ghép lộn xộn thì câu 101 mang nội dung của ô khác, và không có gì báo — cả
    hai đều là câu Part 5 hợp lệ.
    """
    plan = _plan(tmp_path, count=3)
    for index, slot in enumerate(plan.parts[0].slots):
        writer.save_slot(tmp_path, slot, GOOD.replace("expense reports", f"report number {index}"))

    body = loader.raw_text(plan, tmp_path, 5)
    order = [line for line in body.splitlines() if line.startswith("Regional managers")]
    assert order == [
        f"Regional managers must submit their report number {index} "
        f"------- the fifteenth of each month."
        for index in range(3)
    ]


def test_pending_is_a_query_over_the_folder(tmp_path):
    """Hàng đợi là một truy vấn, không phải một bảng job.

    Chạy lại lệnh là tìm thấy ít việc hơn — đó là toàn bộ cơ chế phục hồi, và nó
    đủ vì mọi chặng đều để lại hiện vật trên đĩa.
    """
    plan = _plan(tmp_path, count=3)
    assert len(writer.pending(plan, tmp_path)) == 3
    writer.save_slot(tmp_path, plan.parts[0].slots[1], GOOD)
    assert [slot.id for slot in writer.pending(plan, tmp_path)] == ["p5-01", "p5-03"]


def test_a_blank_written_with_underscores_is_normalised_not_rejected():
    """Sửa ĐỊNH DẠNG thì được, sửa nội dung thì không.

    Mô hình viết `_______` khoảng một trên mười lăm câu. Chuỗi gạch dưới và bảy
    gạch ngang nói cùng một điều ở cùng một chỗ, nên quy về một dạng không giấu
    lỗi nào — còn bắt sinh lại chỉ để đổi ký tự là trả tiền cho một lượt gọi mà
    không đổi gì. Tự sửa một đáp án SAI thành đúng thì ngược lại: nó che mất
    đúng tín hiệu mà cổng kiểm sinh ra để bắt.
    """
    raw = GOOD.replace("-------", "_______")
    assert writer.BLANK in writer.clean(raw)
    # Và phần còn lại không bị đụng tới: dấu gạch trong lời giải thích ở lại.
    explained = GOOD.replace("hạn chót.", "hạn chót --- không phải khoảng thời gian.")
    assert "--- không phải" in writer.clean(explained)


def test_the_form_level_gate_catches_answer_position_bias(tmp_path):
    """Lỗi ở tầng ĐỀ, không tầng câu — nên không phép kiểm từng câu nào thấy.

    Đo được trên một lượt chạy thật với model 550B: **29/30 câu có đáp án là
    (A)**, tức người chọn bừa A được 97%. Mỗi câu riêng lẻ hoàn toàn hợp lệ.
    """
    from app.content.exam import check as gate

    plan = _plan(tmp_path, count=10)
    for slot in plan.parts[0].slots:
        writer.save_slot(tmp_path, slot, GOOD)  # GOOD có `Answer: A`

    problems = gate.check_answer_spread(tmp_path, plan)
    assert len(problems) == 1
    assert "(A)" in problems[0] and "100%" in problems[0]


def test_balancing_spreads_the_key_and_is_safe_to_repeat(tmp_path):
    """Hoán vị là phép biến đổi ĐỊNH DẠNG: cùng bốn phương án, cùng phương án đúng.

    Và nó chạy lại được: "đưa đáp án đúng về chữ X" là một đích cố định, nên lần
    chạy thứ hai không xê dịch gì. Không có tính chất đó thì mỗi lần chạy lại là
    một lần xáo tiếp, và hai người chạy cùng blueprint sẽ ra hai đề khác nhau.
    """
    from app.content.exam import balance as balancer
    from app.content.exam.check import parse_one

    plan = _plan(tmp_path, count=8)
    for slot in plan.parts[0].slots:
        writer.save_slot(tmp_path, slot, GOOD)

    first = balancer.balance(plan, tmp_path)
    assert max(first.values()) <= 2, first
    assert sum(first.values()) == 8

    # Nội dung của phương án đúng KHÔNG đổi, chỉ đổi chỗ.
    question, _ = parse_one(
        (tmp_path / "paste" / plan.parts[0].slots[1].id).with_suffix(".txt").read_text()
    )
    assert question is not None
    correct = next(option.content for option in question.options if option.is_correct)
    assert correct == "by"

    assert balancer.balance(plan, tmp_path) == first, "chạy lại phải ra đúng kết quả cũ"


def test_pruning_deletes_the_paste_file_so_the_slot_returns_to_the_queue(tmp_path):
    """Loại = XOÁ tệp, không phải đánh dấu.

    Hàng đợi của chặng sinh là một truy vấn trên thư mục ("ô nào chưa có tệp"),
    nên xoá tệp chính là đưa ô đó trở lại hàng đợi. Một cột `status` bên cạnh sẽ
    là trạng thái thứ hai phải giữ đồng bộ với sự tồn tại của tệp, và hai nguồn
    sự thật cho cùng một câu hỏi là chỗ chúng lệch nhau.
    """
    plan = _plan(tmp_path, count=2)
    good, bad = plan.parts[0].slots
    writer.save_slot(tmp_path, good, GOOD)
    writer.save_slot(tmp_path, bad, GOOD.replace("Source: original", ""))

    assert writer.pending(plan, tmp_path) == []
    reports = {r.slot_id: r for r in checker.check_blueprint(plan, tmp_path)}
    assert not reports[good.id].blocked
    assert reports[bad.id].blocked

    writer.paste_path(tmp_path, bad).unlink()
    assert [slot.id for slot in writer.pending(plan, tmp_path)] == [bad.id]


def test_backoff_retries_a_read_timeout(monkeypatch):
    """Hết giờ đọc là lỗi TẠM THỜI dù không mang mã số nào.

    Một model suy luận chậm vượt hạn giờ ở lượt đầu rồi trả lời bình thường ở
    lượt sau. Vì thông báo không chứa "503", bản đầu của `with_backoff` ném
    thẳng ra và cả ô bị bỏ qua — im lặng, vì vòng lặp chỉ ghi một dòng lỗi rồi
    đi tiếp.
    """
    from app.services.llm.base import LLMError, LLMResult, Usage
    from app.services.llm.retry import with_backoff

    calls = {"n": 0}

    def flaky() -> LLMResult:
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMError("không gọi được tokenrouter: The read operation timed out")
        return LLMResult(text="ok", usage=Usage(), model="m", provider="p")

    assert with_backoff(flaky, tries=2, delay=0.01).text == "ok"
    assert calls["n"] == 2


PART1_GOOD = """[QUESTION]
voice: us_female_1
(A) The man is typing on a keyboard.
(B) The man is holding a telephone.
(C) Two people are in the office.
(D) The desk is covered with papers.
Answer: A
Source: original
"""


def test_a_part_1_block_is_read_as_four_spoken_statements_not_four_empty_ones(tmp_path):
    """Part 1 KHÔNG in gì, nên chữ nằm ở `spoken_text` và `content` là NULL.

    Đây là chỗ mọi phép kiểm ngữ nghĩa tắt lặng lẽ: đọc thẳng `option.content`
    thì bốn lựa chọn thành bốn chuỗi rỗng, và phép "có hai lựa chọn trùng nhau"
    báo trùng ở **mọi** câu — thấy được. Nguy hơn là phép chống trùng đề bài, vốn
    đọc `prompt_text`: nó cho ra chuỗi rỗng ở mọi ô và tắt hẳn, ở đúng part dễ
    lặp nhất, mà không báo gì.
    """
    plan = bp.build_part1("tp-test", "Test", seed=1)
    plan.parts[0].slots = plan.parts[0].slots[:2]
    photos = tmp_path / "photos"
    photos.mkdir()
    for slot in plan.parts[0].slots:
        writer.save_slot(tmp_path, slot, PART1_GOOD.replace("us_female_1", slot.voice))
        (photos / f"{slot.id}.txt").write_text("A photograph of one man at a desk.")

    reports = checker.check_blueprint(plan, tmp_path)
    # Ô thứ nhất sạch; ô thứ hai lặp lại y hệt nên phải bị bắt là trùng.
    assert reports[0].problems == []
    assert reports[0].flags == []
    assert any("trùng" in problem for problem in reports[1].problems)


def test_planning_a_second_part_keeps_the_first(tmp_path):
    """`plan` cộng dồn. Ghi đè thì tệp dán của part cũ vẫn nằm nguyên trên đĩa,
    nên không có gì báo cho tới khi `check` nói "0 ô" về một part đã viết xong.
    """
    part5 = bp.build_part5("tp-test", "Test", seed=1, count=3)
    both = bp.merge(part5, bp.build_part1("tp-test", "Test", seed=1))
    assert [plan.part for plan in both.parts] == [1, 5]
    # Lập lại kế hoạch cùng một part thì THAY, không nhân đôi.
    again = bp.merge(both, bp.build_part1("tp-test", "Test", seed=1))
    assert [plan.part for plan in again.parts] == [1, 5]
    assert again.slot_count() == 9


def test_balancing_one_part_leaves_the_other_untouched(tmp_path):
    """Gán đích TRONG từng part.

    Gán trên danh sách gộp thì thêm một part mới sẽ dịch đích của mọi part đã cân
    trước đó — các tệp dán bị viết lại và không còn khớp với những gì đã nằm
    trong database.
    """
    from app.content.exam import balance as balancer

    plan = bp.merge(
        bp.build_part5("tp-test", "Test", seed=1, count=3),
        bp.build_part1("tp-test", "Test", seed=1),
    )
    for slot in next(p for p in plan.parts if p.part == 5).slots:
        writer.save_slot(tmp_path, slot, GOOD)
    for slot in next(p for p in plan.parts if p.part == 1).slots:
        writer.save_slot(tmp_path, slot, PART1_GOOD.replace("us_female_1", slot.voice))

    before = {
        slot.id: writer.paste_path(tmp_path, slot).read_text()
        for slot in next(p for p in plan.parts if p.part == 5).slots
    }
    balancer.balance(plan, tmp_path, only=1)
    after = {
        slot.id: writer.paste_path(tmp_path, slot).read_text()
        for slot in next(p for p in plan.parts if p.part == 5).slots
    }
    assert before == after


def test_a_negative_clause_becomes_an_avoid_not_part_of_the_drawing_prompt():
    """Mô hình khuếch tán không có phủ định: "no telephone" đọc ra gần như
    "telephone". Câu phủ định là thứ làm ba câu nhiễu sai kiểm chứng được, nên nó
    phải tồn tại — chỉ là ở vế `Avoid`, không ở vế vẽ.

    Cắt tới mức MỆNH ĐỀ, không tới câu: phủ định thường nấp ở nửa sau một câu
    ghép, và cắt theo dấu chấm thôi thì cả câu đó bị xếp vào vế khẳng định.
    """
    from app.content.exam.photos import photo_prompt

    prompt, avoid = photo_prompt(
        "A photograph of one man at a desk. Both hands are on the keyboard; "
        "no telephone is visible. No other people are visible."
    )
    assert "telephone" not in prompt
    assert "other people" not in prompt
    assert "telephone" in avoid
    assert "other people" in avoid
    assert "one man at a desk" in prompt


def test_part_1_must_carry_all_three_picture_shapes():
    """Ràng buộc ở tầng ĐỀ, không tầng câu.

    Sáu tấm ảnh cùng một dạng qua sạch mọi phép kiểm từng câu — mỗi câu vẫn hợp
    lệ — và người học chỉ phát hiện ra mình chưa từng gặp tranh không có người
    vào lúc ngồi trong phòng thi. Cùng hình dạng với thiên lệch vị trí đáp án,
    thứ cũng phải sửa bằng một cổng riêng ở tầng đề.
    """
    plan = bp.build_part1("tp-test", "Test", seed=1)
    assert bp.validate(plan) == []
    assert {slot.people for slot in plan.parts[0].slots} == set(bp.PEOPLE_SHAPES)

    # Bỏ dạng "không người" đi thì blueprint phải từ chối, trước khi nó tốn một
    # lượt gọi nào.
    for slot in plan.parts[0].slots:
        if slot.people == "none":
            slot.people = "one"
            slot.question_type = "PART_1_PERSON_DESCRIPTION"
    problems = bp.validate(plan)
    assert any("thiếu dạng tranh" in problem and "none" in problem for problem in problems)


def test_the_voice_line_is_given_verbatim_not_described():
    """Mô hình nhỏ chép nguyên cả dấu ngoặc ngược nếu prompt mô tả dòng cần in.

    Bản cũ viết "Dòng `voice:` phải ghi đúng: ca_male_1" và gemma3 xuất ra
    `` `voice:` ca_male_1 `` — parser từ chối, ba lần liên tiếp y hệt nhau. Lỗi
    của prompt, không phải của mô hình.
    """
    plan = bp.build_part1("tp-test", "Test", seed=1)
    text = writer.prompt_for_part1(plan.parts[0].slots[0])
    assert "\nvoice: " in text
    assert "`voice:`" not in text


def test_greyscale_is_asked_for_in_the_prompt_and_forced_afterwards():
    """Làm CẢ HAI, và mỗi vế chữa một kiểu hỏng khác nhau.

    Chỉ ép về đơn sắc thì mô hình bố cục theo màu, và bản khử màu của một cảnh
    hợp lý về màu có thể mất hết tương phản giữa chủ thể và nền. Chỉ xin thì mô
    hình vẫn trả ảnh màu ở một số lượt, và cái sai đó chỉ lộ ra khi có người
    nhìn — đúng loại lỗi mà một phép biến đổi tất định xoá sạch.
    """
    from app.content.exam.photos import photo_prompt

    prompt, avoid = photo_prompt("A photograph of one man at a desk.")
    assert "black and white" in prompt
    assert "colour" in avoid


def test_greyscale_conversion_keeps_three_channels(tmp_path):
    """Ghi lại thành RGB chứ không giữ chế độ một kênh.

    Ảnh "L" vẫn hiển thị đúng, nhưng mọi thứ phía sau (đo kích thước, Cloudinary,
    trình duyệt) làm việc với ba kênh, và một định dạng khác thường ở giữa đường
    ống là chỗ hỏng lặng lẽ ở đúng một khâu nào đó.
    """
    from PIL import Image

    from app.content.exam.photos import to_greyscale

    path = tmp_path / "x.png"
    Image.new("RGB", (8, 8), (200, 40, 40)).save(path)
    to_greyscale(path)
    with Image.open(path) as opened:
        assert opened.mode == "RGB"
        red, green, blue = opened.convert("RGB").getpixel((0, 0))
        assert red == green == blue


PART3_GOOD = """[SCRIPT]
voice: au_female_1
Have you looked at the interview schedule for tomorrow?
voice: au_male_1
Yes, but one candidate asked to move to Thursday morning.
voice: au_female_1
That works. I'll book Room B for ten o'clock.

[QUESTION]
What are the speakers discussing?
(A) An interview schedule
(B) A budget report
(C) An office move
(D) A training course
Answer: A
Source: original

[QUESTION]
What problem does the man mention?
(A) A scheduling conflict
(B) A broken laptop
(C) A missing resume
(D) A cancelled flight
Answer: A
Source: original

[QUESTION]
What will the woman do next?
(A) Reserve a room
(B) Email a candidate
(C) Print some forms
(D) Call the manager
Answer: A
Source: original
"""


class _Recorder:
    """Gateway giả chỉ ghi lại yêu cầu và luôn trả về "A"."""

    def __init__(self):
        self.seen = []

    def run(self, request, feature, tier):  # noqa: ANN001, ARG002
        from app.services.llm.base import LLMResult

        self.seen.append(request)
        return LLMResult(text="A", input_tokens=0, output_tokens=0, cached_tokens=0)


def _part3_plan(tmp_path):
    plan = bp.build_part3("tp-test", "Test", seed=7)
    plan.parts[0].slots = plan.parts[0].slots[:1]
    writer.save_slot(tmp_path, plan.parts[0].slots[0], PART3_GOOD)
    return plan


def test_a_part_3_paste_file_becomes_three_reports(tmp_path):
    """Đơn vị SINH là cả cụm, đơn vị ĐỌC là từng câu.

    Ba câu hỏi về cùng một đoạn thoại phải viết cùng nhau, nên `prune` chỉ xoá
    được cả cụm. Nhưng người duyệt cần biết câu nào trong ba câu có vấn đề, nên
    mỗi câu có báo cáo riêng, đánh đúng số câu của nó.
    """
    plan = _part3_plan(tmp_path)
    reports = checker.check_blueprint(plan, tmp_path, only=3)
    assert [report.number for report in reports] == [32, 33, 34]
    assert all(report.problems == [] for report in reports)


def test_the_judge_is_given_the_conversation_not_just_the_question(tmp_path):
    """Thiếu lời thoại thì phép kiểm VẪN CHẠY và vẫn trả về một chữ cái.

    Đo được: một biến bị bỏ quên làm lời thoại không được gửi đi, và chặng đối
    chiếu báo 26 cờ trên 39 câu — người chấm đang đoán "người nói đang ở đâu" mà
    không được nghe gì. Nối lại thì còn 0 cờ. Không có bài test này thì cách duy
    nhất để phát hiện là thấy tỉ lệ cờ cao rồi tự hỏi vì sao.
    """
    plan = _part3_plan(tmp_path)
    recorder = _Recorder()
    checker.check_blueprint(plan, tmp_path, recorder, Tier.CHEAP, False, 3)  # type: ignore[arg-type]

    assert recorder.seen, "chặng đối chiếu không gọi lượt nào"
    for request in recorder.seen:
        assert "interview schedule for tomorrow" in request.user


def test_a_generic_part_3_stem_may_repeat_across_conversations(tmp_path):
    """ "What will the woman do next?" là khuôn câu chuẩn và lặp lại trong đề THẬT.

    Chống trùng trên riêng đề bài bắt đúng ba câu như thế ở lượt chạy đầu — tin
    nó thì cổng kiểm đang ép mô hình bịa ra câu hỏi không tự nhiên để né chính
    nó. Cái đáng bắt là hai câu giống nhau về CÙNG một đoạn thoại.
    """
    plan = bp.build_part3("tp-test", "Test", seed=7)
    plan.parts[0].slots = plan.parts[0].slots[:2]
    first, second = plan.parts[0].slots
    writer.save_slot(tmp_path, first, PART3_GOOD)
    # Cùng ba đề bài, hội thoại khác — đây là chuyện bình thường.
    writer.save_slot(
        tmp_path, second, PART3_GOOD.replace("interview schedule", "delivery schedule")
    )
    assert all(report.problems == [] for report in checker.check_blueprint(plan, tmp_path, only=3))

    # Hội thoại y hệt thì mới là lỗi, và nó phải được gọi đúng tên.
    writer.save_slot(tmp_path, second, PART3_GOOD)
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=3) for p in r.problems]
    assert any("hội thoại trùng" in problem for problem in problems)


def test_each_question_in_a_set_gets_its_own_answer_target(tmp_path):
    """Cân theo TỆP thì `rewrite` gặp lựa chọn của câu đầu và `Answer:` của câu
    cuối, rồi đổi chỗ hai thứ thuộc hai câu khác nhau — một phép hoán vị vẫn
    "thành công" và làm hỏng hai câu cùng lúc.
    """
    from app.content.exam import balance as balancer

    plan = _part3_plan(tmp_path)
    balancer.balance(plan, tmp_path, only=3)
    text = writer.paste_path(tmp_path, plan.parts[0].slots[0]).read_text()

    # Lời thoại còn nguyên, và ba câu KHÔNG cùng một đáp án.
    assert "[SCRIPT]" in text and "interview schedule" in text
    keys = [line.split(":")[1].strip() for line in text.splitlines() if line.startswith("Answer:")]
    assert len(keys) == 3
    assert len(set(keys)) == 3

    # Và mỗi câu vẫn tự nhất quán: đáp án của nó vẫn là phương án đúng cũ.
    questions, _, problems = checker.parse_group(text, 3)
    assert problems == []
    correct = [next(o for o in q.options if o.is_correct).content for q in questions]
    assert correct == ["An interview schedule", "A scheduling conflict", "Reserve a room"]


GRAPHIC_DATA = """kind: table
Anniversary Package Options
Package | Price
Standard | Eight hundred dollars
Premium | Twelve hundred dollars
Executive | Eighteen hundred dollars
Ultimate | Twenty-four hundred dollars
"""

PART3_GRAPHIC = """[SCRIPT]
voice: au_female_1
We have a budget of about eighteen hundred dollars for the anniversary event.
voice: au_male_1
Then there's one package that fits exactly. I'll book it this afternoon.

[QUESTION]
What event are the speakers planning?
(A) A company anniversary
(B) A product launch
(C) A training day
(D) A retirement party
Answer: A
Source: original

[QUESTION]
What will the man do this afternoon?
(A) Book a package
(B) Call a caterer
(C) Email the budget
(D) Visit a venue
Answer: A
Source: original

[QUESTION]
Look at the graphic. Which package will the speakers choose?
(A) Standard
(B) Premium
(C) Executive
(D) Ultimate
Answer: C
Source: original
"""


def _graphic_plan(tmp_path, data=GRAPHIC_DATA, block=PART3_GRAPHIC):
    plan = bp.build_part3("tp-test", "Test", seed=7)
    slot = next(s for s in plan.parts[0].slots if s.graphic)
    plan.parts[0].slots = [slot]
    writer.save_slot(tmp_path, slot, block)
    (tmp_path / "graphics").mkdir(exist_ok=True)
    (tmp_path / "graphics" / f"{slot.id}.txt").write_text(data)
    return plan


def test_the_graphic_options_must_be_the_answer_axis_of_its_kind(tmp_path):
    """Bốn lựa chọn của câu cuối phải đúng là TRỤC ĐÁP ÁN của hình.

    Trục đó khác nhau theo dạng — đo ở đề mẫu ETS, câu 64 hỏi giữa bốn loại sổ
    (tên hàng của bảng), câu 67 giữa bốn khung giờ (tiêu đề CỘT của lưới lịch),
    câu 70 giữa bốn cửa hàng (ô của sơ đồ). Lấy nhầm trục thì câu hỏi vẫn hợp lệ
    về mọi mặt và vẫn có đúng một đáp án — nó chỉ không còn hỏi về tấm hình.
    """
    plan = _graphic_plan(tmp_path)
    assert all(r.problems == [] for r in checker.check_blueprint(plan, tmp_path, only=3))

    plan = _graphic_plan(
        tmp_path,
        block=PART3_GRAPHIC.replace("(A) Standard", "(A) The cheapest one"),
    )
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=3) for p in r.problems]
    assert any("trục đáp án của hình" in problem for problem in problems)


def test_a_conversation_that_names_the_answer_row_is_flagged(tmp_path):
    """Nếu có người nói thẳng "Executive" thì câu trả lời được ngay từ audio.

    Mọi thứ khác vẫn hợp lệ — câu vẫn có đúng một đáp án, bốn lựa chọn vẫn là
    bốn hàng — chỉ là nó không còn là câu hỏi về hình. Không phép kiểm nào khác
    thấy được.
    """
    plan = _graphic_plan(
        tmp_path,
        block=PART3_GRAPHIC.replace(
            "Then there's one package that fits exactly.",
            "Then the Executive package fits exactly.",
        ),
    )
    flags = [f for r in checker.check_blueprint(plan, tmp_path, only=3) for f in r.flags]
    assert any("đọc thẳng tên hàng" in flag for flag in flags)


def test_the_judge_is_shown_the_table_as_well_as_the_conversation(tmp_path):
    """Câu "Look at the graphic" được viết sao cho hội thoại KHÔNG đọc tên hàng
    là đáp án — nên đưa mỗi lời thoại vào là hỏi một câu không thể trả lời, và
    người chấm vẫn trả về một chữ cái. Cùng kiểu mù đã gắn cờ oan 26 câu.
    """
    plan = _graphic_plan(tmp_path)
    recorder = _Recorder()
    checker.check_blueprint(plan, tmp_path, recorder, Tier.CHEAP, False, 3)  # type: ignore[arg-type]
    assert recorder.seen
    assert all("Anniversary Package Options" in request.user for request in recorder.seen)


def test_a_graphic_and_a_graphic_question_must_come_together():
    """Cả hai chiều, vì cả hai đều hỏng lặng lẽ: một câu bảo "nhìn vào hình" khi
    không có hình nào, hay một tấm hình mà không câu nào hỏi tới.
    """
    plan = bp.build_part3("tp-test", "Test", seed=7)
    slot = next(s for s in plan.parts[0].slots if s.graphic)
    slot.graphic = ""
    assert any("không có hình" in problem for problem in bp.validate(plan))

    plan = bp.build_part3("tp-test", "Test", seed=7)
    slot = next(s for s in plan.parts[0].slots if s.graphic)
    slot.question_types[-1] = "PART_3_FUTURE_ACTION"
    assert any("không câu nào hỏi tới" in problem for problem in bp.validate(plan))


# Cố ý KHÔNG dùng số liệu của ví dụ trong prompt: cổng chống chép ví dụ sẽ bắt
# nó, và nó bắt đúng — một fixture trùng ví dụ là chính cái lỗi cổng đó tồn tại
# để chặn.
SCHEDULE_DATA = """kind: schedule
Friday Coverage
Person | 1-2 | 2-3 | 3-4 | 4-5
Noor | Inventory |  |  | Handover
Petra |  | Supplier call |  | Handover
"""

PART3_SCHEDULE = """[SCRIPT]
voice: au_female_1
Noor here. Let's find an hour on Friday when neither of us is booked.
voice: au_male_1
Petra speaking — looking at it now, there's exactly one hour free for both.

[QUESTION]
What are the speakers trying to arrange?
(A) A meeting time
(B) A client visit
(C) A budget review
(D) A team lunch
Answer: A
Source: original

[QUESTION]
What does the man do?
(A) Check a schedule
(B) Call a client
(C) Book a room
(D) Send an invitation
Answer: A
Source: original

[QUESTION]
Look at the graphic. When will the speakers most likely meet?
(A) 1-2
(B) 2-3
(C) 3-4
(D) 4-5
Answer: C
Source: original
"""


def test_a_schedule_answers_on_its_columns_and_keeps_empty_cells(tmp_path):
    """Lưới lịch là dạng dễ hỏng nhất, vì hai chi tiết ngược với bảng.

    Trục đáp án là tiêu đề CỘT (khung giờ), không phải tên hàng (tên người). Và
    ô được phép TRỐNG — câu "họ sẽ họp lúc mấy giờ" trả lời được chính nhờ tìm
    cột mà cả hai hàng đều trống, nên một bản đọc bỏ ô rỗng sẽ xoá đúng dữ kiện
    mà câu hỏi dựa vào.
    """
    from app.content.exam.graphics import parse_graphic

    graphic = parse_graphic(SCHEDULE_DATA)
    assert graphic.problems() == []
    assert graphic.answer_axis() == ["1-2", "2-3", "3-4", "4-5"]
    # Hàng của Noor có hai ô TRỐNG ở giữa — những khung giờ cô ấy rảnh.
    assert graphic.rows[0] == ["Noor", "Inventory", "", "", "Handover"]

    plan = _graphic_plan(tmp_path, data=SCHEDULE_DATA, block=PART3_SCHEDULE)
    assert all(r.problems == [] for r in checker.check_blueprint(plan, tmp_path, only=3))


def test_a_voice_name_can_never_be_a_printed_option(tmp_path):
    """`uk_female_1` là chỉ dẫn thu âm, không phải một con người.

    Nhưng nó nằm ngay trong prompt, nên mô hình nhỏ chép thẳng vào phần IN RA.
    Đo được: một cụm Part 3 có ba trong bốn lựa chọn là tên giọng — và triệu
    chứng đầu tiên không phải một cờ nào cả, mà là người chấm nghĩ 22 000 ký tự
    rồi hết hạn mức mà không trả lời được, vì câu hỏi vô nghĩa.

    Đây là VẤN ĐỀ chứ không phải cờ: không có cách đọc nào khiến nó đúng.
    """
    plan = _part3_plan(tmp_path)
    writer.save_slot(
        tmp_path,
        plan.parts[0].slots[0],
        PART3_GOOD.replace("(B) A budget report", "(B) uk_female_1"),
    )
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=3) for p in r.problems]
    assert any("TÊN GIỌNG" in problem for problem in problems)


def test_the_people_in_a_schedule_must_be_in_the_conversation(tmp_path):
    """Bảng và hội thoại phải nói về CÙNG một nhóm người.

    Đo được: bảng ghi Liam và Emma trong khi hai người nói tên là Sarah và
    James — câu hỏi "khi nào cả hai đều rảnh" không có đáp án. Mọi cổng khác vẫn
    xanh: bảng hợp lệ, bốn lựa chọn khớp trục đáp án, câu vẫn có đúng một
    `Answer:`. Chỉ phép so tên mới thấy.
    """
    plan = _graphic_plan(
        tmp_path,
        data=SCHEDULE_DATA.replace("Noor", "Liam").replace("Petra", "Emma"),
        block=PART3_SCHEDULE,
    )
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=3) for p in r.problems]
    assert any("không xuất hiện trong hội thoại" in problem for problem in problems)


def test_the_graphic_question_sits_where_its_part_puts_it():
    """Part 3 hỏi về hình ở câu thứ BA, Part 4 ở câu thứ HAI.

    Đo ở đề mẫu ETS: câu 64, 67, 70 so với câu 96, 99. Suy ra "luôn là câu cuối"
    từ Part 3 rồi áp cho Part 4 là sai đúng một chi tiết mà người luyện đề nhận
    ra ngay — và cổng kiểm sẽ đi kiểm nhầm câu, một câu vẫn có bốn lựa chọn hợp
    lệ nên nó vẫn cho ra kết luận.
    """
    for part, builder, position in ((3, bp.build_part3, 2), (4, bp.build_part4, 1)):
        plan = builder("tp-test", "Test", seed=7)
        slot = next(s for s in plan.parts[0].slots if s.graphic)
        assert slot.question_types.index(bp.graph_code(part)) == position
        assert bp.GRAPHIC_POSITION[part] == position

        # Dời nó đi một chỗ thì blueprint phải từ chối, trước khi tốn lượt gọi.
        moved = builder("tp-test", "Test", seed=7)
        target = next(s for s in moved.parts[0].slots if s.graphic)
        types = target.question_types
        types[0], types[position] = types[position], types[0]
        assert any("câu hỏi về hình" in problem for problem in bp.validate(moved))


def test_only_one_question_in_a_set_looks_at_the_graphic(tmp_path):
    """Đề thật không bao giờ có hai câu "Look at the graphic" trong một cụm.

    Khi mô hình viết hai, CẢ HAI đều dùng đúng trục đáp án nên phép so trục vẫn
    xanh. Cái mất là câu còn lại: nó lẽ ra hỏi một dạng khác, và cụm mất một
    dạng câu mà blueprint đã giao.
    """
    plan = _graphic_plan(
        tmp_path,
        block=PART3_GRAPHIC.replace(
            "What will the man do this afternoon?",
            "Look at the graphic. Which package is cheapest?",
        ),
    )
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=3) for p in r.problems]
    assert any("chỉ một câu" in problem for problem in problems)


def test_a_graphic_copied_from_the_prompt_example_is_rejected(tmp_path):
    """Mô hình chép nguyên ví dụ trong prompt khá thường.

    Nó không sai về hình thức nên không cổng nào khác thấy — nhưng hai đề sinh
    bằng cùng prompt sẽ dùng chung một tấm hình, và người luyện nhiều đề nhận ra
    ngay. Bắt theo QUÁ NỬA số hàng: mô hình hay đổi đúng một con số rồi giữ
    nguyên phần còn lại.
    """
    from app.content.exam import writer as w

    example = "\n".join(
        ["kind: chart", "Quarterly Sales in thousands"]
        + [
            line.strip()
            for line in w._GRAPHIC_RULES_TEMPLATE.splitlines()
            if line.strip().startswith(
                ("First quarter", "Second quarter", "Third quarter", "Fourth quarter")
            )
        ]
    )
    plan = _graphic_plan(
        tmp_path,
        data=example,
        block=PART3_GRAPHIC.replace("(A) Standard", "(A) First quarter")
        .replace("(B) Premium", "(B) Second quarter")
        .replace("(C) Executive", "(C) Third quarter")
        .replace("(D) Ultimate", "(D) Fourth quarter"),
    )
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=3) for p in r.problems]
    assert any("chép nguyên ví dụ" in problem for problem in problems)
