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
