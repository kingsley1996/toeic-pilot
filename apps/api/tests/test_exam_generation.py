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

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_part1_pool_is_wide_and_carries_all_three_shapes():
    """Pool tĩnh phải đủ rộng để fallback không tái chế đúng sáu cảnh ấy mãi.

    Bản 18 mẫu khiến mọi đề không-`--model` cùng rơi vào dải văn phòng–họp–kho.
    Giữ một ngưỡng tối thiểu và đủ ba dạng tranh để người ra đề không vô tình
    thu hẹp lại `PART1_MIX` khi chỉnh nội dung.
    """
    from app.content.exam.mixes import PART1_MIX

    shapes = {slot[1] for slot in PART1_MIX}
    assert shapes == set(bp.PEOPLE_SHAPES)
    assert len(PART1_MIX) >= 36
    scenes = [slot[2] for slot in PART1_MIX]
    assert len(set(scenes)) == len(scenes), "bối cảnh trùng nhau trong PART1_MIX"


def test_part1_avoid_compresses_history_to_motifs(tmp_path: Path, monkeypatch):
    """Cơ chế chống trùng làm việc ở tầng motif, không ở tầng chuỗi.

    Hai câu khác từng chữ nhưng cùng một nguyên mẫu ("công trường") là đúng thứ
    khiến model tưởng nó đang viết mới. List motif GỘP chúng lại thành MỘT mục
    duy nhất — đó là điểm toàn bộ cơ chế tồn tại — và đề đang chạy không bị
    chính bối cảnh cũ của nó trói.
    """
    from app.content.exam_cli import plan

    def _write(root: Path, slug: str, context: str) -> None:
        form = bp.build_part1(slug, slug, seed=1)
        for slot in form.parts[0].slots:
            slot.context = context  # ghim motif để phép kiểm xác định được
        (root / slug).mkdir(parents=True)
        bp.save(form, root / slug / "blueprint.json")

    # Hai đề cũ, cùng motif "công trường" bằng hai chuỗi khác nhau.
    history = tmp_path / "history"
    _write(history, "tp-old-a", "một công nhân xây dựng đang buộc cốt thép")
    _write(history, "tp-old-b", "thợ hồ đang trát tường trên giàn giáo")
    monkeypatch.setattr(plan, "DEFAULT_ROOT", history)

    avoid, _ = plan._part1_avoid_and_lean("tp-new", seed=7)
    assert "công trường" in avoid
    assert avoid.count("công trường") == 1, "motif phải gộp về một mục, không liệt từng câu"
    assert "giàn giáo" not in avoid and "cốt thép" not in avoid, "không được đống cả câu văn"

    # Chạy lại chính đề A: motif của nó bị loại trừ (đường gọi có exclude_slug).
    solo = tmp_path / "solo"
    _write(solo, "tp-old-a", "một công nhân xây dựng đang buộc cốt thép")
    monkeypatch.setattr(plan, "DEFAULT_ROOT", solo)
    assert plan._part1_avoid_and_lean("tp-old-a", seed=7) == ("", "")
    assert "công trường" in plan._part1_avoid_and_lean("tp-fresh", seed=7)[0]


def test_part1_avoid_is_a_sliding_window_not_all_history(tmp_path: Path, monkeypatch):
    """Cảnh cũ phải được quay vòng sau `PART1_AVOID_WINDOW` đề.

    Nếu tránh MỌI đề từng tồn tại thì sau ~10 đề `used` phủ kín bảng motif,
    `avoid` thành "đừng vẽ cảnh TOEIC nào" và `lean` rỗng vĩnh viễn. Cửa sổ recency
    (mtime) cắt phần cũ đi — đây là điểm phân biệt sổ-trượt với-cấm-vĩnh-viễn.
    """
    import os

    from app.content.exam_cli import plan

    monkeypatch.setattr(plan, "DEFAULT_ROOT", tmp_path)
    monkeypatch.setattr(plan, "PART1_AVOID_WINDOW", 2)

    def _write(slug: str, context: str, stamp: int) -> None:
        form = bp.build_part1(slug, slug, seed=1)
        for slot in form.parts[0].slots:
            slot.context = context
        (tmp_path / slug).mkdir(parents=True)
        path = tmp_path / slug / "blueprint.json"
        bp.save(form, path)
        os.utime(path, (stamp, stamp))  # ghim recency, đừng tin mtime tự nhiên

    _write("tp-stale", "một công nhân xây dựng đang buộc cốt thép", stamp=100)  # cũ nhất
    _write("tp-mid", "bệnh nhân ngồi chờ ở phòng khám", stamp=200)
    _write("tp-new", "hành khách lần lượt bước lên xe buýt", stamp=300)  # mới nhất

    # Window=2 → chỉ hai đề mới nhất được tính; "công trường" rơi khỏi cửa sổ.
    avoid, _ = plan._part1_avoid_and_lean("tp-brand-new", seed=7)
    assert "công trường" not in avoid, "motif ngoài cửa sổ phải được quay vòng, không cấm mãi"
    assert "y tế / phòng khám" in avoid and "xe buýt / giao thông công cộng" in avoid

    # Cùng dữ liệu nhưng window rộng hơn → "công trường" quay lại đúng vai motif
    # đã-dùng: chứng minh nó bị cắt bởi CỬA SỔ, không phải bị bug bỏ sót.
    monkeypatch.setattr(plan, "PART1_AVOID_WINDOW", 3)
    avoid_wide, _ = plan._part1_avoid_and_lean("tp-brand-new", seed=7)
    assert "công trường" in avoid_wide


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
(B) A candidate's flight on Thursday
(C) A room booked for tomorrow morning
(D) A training course
Answer: A
Source: original

[QUESTION]
What problem does the man mention?
(A) A scheduling conflict
(B) A candidate cancelled an interview
(C) Room B is taken at ten o'clock
(D) A missing resume
Answer: A
Source: original

[QUESTION]
What will the woman do next?
(A) Reserve a room for the Thursday candidate
(B) Interview a candidate at ten o'clock
(C) Move the schedule to Thursday morning
(D) Print some forms
Answer: A
Source: original
"""


def _result(text: str):  # type: ignore[no-untyped-def]
    """`LLMResult` tối thiểu cho các gateway giả."""
    from app.services.llm.base import LLMResult, Usage

    return LLMResult(text=text, usage=Usage(), model="fake", provider="fake")


class _Recorder:
    """Gateway giả chỉ ghi lại yêu cầu và luôn trả về "A"."""

    def __init__(self):
        self.seen = []

    def run(self, request, feature, tier):  # noqa: ANN001, ARG002
        self.seen.append(request)
        return _result("A")


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
    # Lấy hai ô KHÔNG có câu hàm ý, thay vì hai ô đầu. `PART3_GOOD` là một hội
    # thoại thường; ô mang `PART_3_IMPLICATION` đòi một lời trích có thật trong
    # lời thoại (`check_implication`), nên dùng nó ở đây sẽ đỏ vì một lý do
    # chẳng liên quan tới chống trùng. Bảng mix nay được xáo theo seed, nên
    # "hai ô đầu" không còn là một hình dạng cố định.
    plain = [s for s in plan.parts[0].slots if "PART_3_IMPLICATION" not in s.question_types]
    plan.parts[0].slots = plain[:2]
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
    assert correct == [
        "An interview schedule",
        "A scheduling conflict",
        "Reserve a room for the Thursday candidate",
    ]


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
(B) An eighteen-hundred-dollar refund
(C) A package booked last afternoon
(D) A retirement party
Answer: A
Source: original

[QUESTION]
What will the man do this afternoon?
(A) Book a package
(B) Raise the event budget
(C) Ask about a cheaper package
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
    # `hard` tắt: các bài dùng fixture này ghim LUẬT HÌNH. Bắt nó thoả thêm trục
    # D1 làm mỗi lần sửa luật độ khó lại phải sửa một fixture nói về chuyện khác.
    slot.hard = 0
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
(B) An hour booked on Friday
(C) A free hour for one of them
(D) A team lunch
Answer: A
Source: original

[QUESTION]
What does the man do?
(A) Check a schedule
(B) Book an hour on Friday
(C) Tell Noor he is free all day
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


def test_the_spread_gate_blocks_on_a_hard_slot_and_only_flags_elsewhere(tmp_path):
    """Cột `hard` của blueprint quyết định phép đo này CHẶN hay chỉ gắn cờ.

    Một mức duy nhất không dùng được. Chặn tất cả thì mọi ô của các đề đã sinh
    hoá đỏ — đo trên `tp-form-11`: 3 trên 13 cụm Part 3 dính. Cờ tất cả thì trục
    D1 không bao giờ được cưỡng chế, và `SPEC-EXAM-DIFFICULTY` §1 đã đo rằng
    thiếu cổng thì mix chỉ là gợi ý. Nên ô mang `hard` phải đạt, ô không mang
    giữ nguyên hành vi cũ.
    """
    # Bản cũ của fixture: cả ba đáp án nằm gọn trong một câu văn — và cả ba phải
    # ĐO ĐƯỢC, nếu không cổng im theo luật ở `test_an_unmeasurable_answer…`.
    # "A scheduling conflict" không dùng chữ nào của lời thoại, nên phải đổi.
    easy = PART3_GOOD.replace(
        "(A) Reserve a room for the Thursday candidate", "(A) Reserve a room"
    ).replace("(A) A scheduling conflict", "(A) A candidate asked to move")
    plan = bp.build_part3("tp-test", "Test", seed=7)
    slot = plan.parts[0].slots[0]
    plan.parts[0].slots = [slot]
    writer.save_slot(tmp_path, slot, easy)

    assert slot.hard, "build_part3 phải đánh dấu cụm ba câu là hard"
    blocked = checker.check_blueprint(plan, tmp_path, only=3)
    assert any("ghép hai chỗ tách rời" in problem for r in blocked for problem in r.problems)

    slot.hard = 0
    lenient = checker.check_blueprint(plan, tmp_path, only=3)
    assert all(r.problems == [] for r in lenient)
    assert any("ghép hai chỗ tách rời" in flag for r in lenient for flag in r.flags)


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
        PART3_GOOD.replace("(B) A candidate's flight on Thursday", "(B) uk_female_1"),
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
            for line in w.GRAPHIC_RULES_TEMPLATE.splitlines()
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


PART2_GOOD = """[QUESTION]
voice: us_female_1
Where did you put the quarterly sales report?
voice: uk_male_1
(A) On your desk, next to the printer.
(B) Yes, I finished it last night.
(C) About thirty copies, I think.
Answer: A
Source: original
"""


def test_part_2_balances_across_three_letters_not_four(tmp_path):
    """Part 2 chỉ có ba đáp án, và gán đích `D` là một lần BỎ QUA IM LẶNG.

    `rewrite` không tìm thấy lựa chọn `D` nên trả về khối y nguyên — một phần tư
    số câu giữ nguyên vị trí đáp án mô hình đã chọn, trong khi phép cân báo đã
    chạy xong. `balance.py` đã ghi trước là sẽ gặp chuyện này khi tới lượt Part 2.
    """
    from app.content.exam import balance as balancer

    plan = bp.build_part2("tp-test", "Test", seed=3)
    plan.parts[0].slots = plan.parts[0].slots[:6]
    for slot in plan.parts[0].slots:
        writer.save_slot(tmp_path, slot, PART2_GOOD.replace("us_female_1", slot.voices[0]))

    tally = balancer.balance(plan, tmp_path, only=2)
    assert tally["D"] == 0
    # Sáu câu, ba chữ cái: đúng hai câu mỗi chữ.
    assert sorted(tally[letter] for letter in "ABC") == [2, 2, 2]


class _Replies:
    """Gateway giả trả về đúng một khối cho trước."""

    def __init__(self, text: str):
        self.text = text

    def run(self, request, feature, tier):  # noqa: ANN001, ARG002
        return _result(self.text)


def test_a_part_2_block_is_complete_without_a_d_option():
    """Phép kiểm "khối hoàn chỉnh" của `write_slot` đòi có dòng `(D)`.

    Ở Part 2 đó là dấu hiệu SAI, nên mọi ô viết đúng đều bị NÉM ĐI trước khi kịp
    lưu — và ô bị ném thì quay lại hàng đợi, nên lượt chạy sau lặp đúng như thế,
    mãi mãi.

    Bài này phải gọi `write_slot`, không phải `check_blueprint`: luật `(D)` nằm ở
    chặng viết. Bản đầu của nó kiểm nhầm chặng và **vẫn xanh khi gỡ bản sửa** —
    một bài test không kiểm thứ nó nói thì tệ hơn là không có, vì nó khiến ta
    tin là đã được che.
    """
    plan = bp.build_part2("tp-test", "Test", seed=3)
    slot = plan.parts[0].slots[0]
    block = PART2_GOOD.replace("us_female_1", slot.voices[0])
    assert writer.write_slot(_Replies(block), slot, Tier.CHEAP, 2).startswith("[QUESTION]")


def test_part_2_needs_two_different_voices():
    """Người hỏi và người đáp là hai người.

    Một giọng cho cả bốn lượt nói thì người nghe không tách được câu hỏi khỏi ba
    câu đáp, và cả dạng câu này mất nghĩa — nhưng bản thu vẫn phát ra bình
    thường, nên chỉ nghe mới biết.
    """
    plan = bp.build_part2("tp-test", "Test", seed=3)
    assert bp.validate(plan) == []
    assert all(len(set(slot.voices)) == 2 for slot in plan.parts[0].slots)

    plan.parts[0].slots[0].voices = ["us_female_1", "us_female_1"]
    assert any("khác giọng" in problem for problem in bp.validate(plan))


PART6_GOOD = """[PASSAGE]
Dear Ms. Vance,

Thank you for your subscription. Your ticket package ------- (1) by Friday. You
will also receive a card granting you ------- (2) such as priority seating.
Please contact ------- (3) with any questions. ------- (4)

Sincerely,
David Cho

[QUESTION]
Blank (1)
(A) ships
(B) will be shipped
(C) was shipping
(D) has been shipping
Answer: B
Source: original

[QUESTION]
Blank (2)
(A) benefits
(B) expenses
(C) positions
(D) materials
Answer: A
Source: original

[QUESTION]
Blank (3)
(A) we
(B) us
(C) our
(D) ourselves
Answer: B
Source: original

[QUESTION]
Blank (4)
(A) Our representatives are available daily to assist you.
(B) The musicians have been rehearsing for months.
(C) Please return the damaged tickets to our box office.
(D) Refunds are processed within ten business days.
Answer: A
Source: original
"""


def test_balancing_never_drops_a_question_block(tmp_path):
    """Thiếu đích thì GIỮ NGUYÊN khối, không bỏ nó đi.

    Bản đầu dùng `zip(..., strict=False)` và chỉ ghi lại những khối ghép được —
    một tệp Part 6 bốn câu chỉ có một đích bị viết lại thành tệp MỘT câu, mất ba
    câu kia vĩnh viễn. Không phải "bỏ qua phép cân": là **xoá nội dung**, và
    lệnh vẫn báo chạy xong. Cả bốn văn bản Part 6 của lượt chạy thật bị ăn mất
    ba phần tư trước khi ai kịp nhìn.
    """
    from app.content.exam import balance as balancer

    # Gọi thẳng `rewrite_all` với MỘT đích cho BỐN khối. Đi qua `balance` thì
    # không tái hiện được: ở đó số đích luôn khớp số khối, nên hai bản sửa
    # (`QUESTIONS_PER_SET` và chỗ này) che cho nhau và bài test xanh dù gỡ một
    # trong hai. Bất biến thuộc về `rewrite_all`, độc lập với người gọi nó.
    text = balancer.rewrite_all(PART6_GOOD, ["C"])
    assert text.count("[QUESTION]") == 4
    assert "[PASSAGE]" in text and "David Cho" in text
    keys = [line.split(":")[1].strip() for line in text.splitlines() if line.startswith("Answer:")]
    # Khối đầu được cân sang C; ba khối sau giữ nguyên đáp án cũ, KHÔNG biến mất.
    assert keys == ["C", "A", "B", "A"]

    # Và khi đủ đích thì cả bốn đều được cân.
    plan = bp.build_part6("tp-test", "Test", seed=3)
    plan.parts[0].slots = plan.parts[0].slots[:1]
    writer.save_slot(tmp_path, plan.parts[0].slots[0], PART6_GOOD)
    balancer.balance(plan, tmp_path, only=6)
    full = writer.paste_path(tmp_path, plan.parts[0].slots[0]).read_text()
    spread = [
        line.split(":")[1].strip() for line in full.splitlines() if line.startswith("Answer:")
    ]
    assert sorted(spread) == ["A", "B", "C", "D"]


def test_a_part_6_text_is_read_as_four_questions_over_one_passage(tmp_path):
    plan = bp.build_part6("tp-test", "Test", seed=3)
    plan.parts[0].slots = plan.parts[0].slots[:1]
    writer.save_slot(tmp_path, plan.parts[0].slots[0], PART6_GOOD)
    reports = checker.check_blueprint(plan, tmp_path, only=6)
    assert [r.number for r in reports] == [131, 132, 133, 134]
    assert all(r.problems == [] for r in reports)


def test_part_6_pins_the_sentence_insertion_to_blank_3_or_4():
    """Đề thật đặt câu điền câu ở blank 3 hoặc 4 — không bao giờ ở 1 hay 2.

    Phần lớn ở cuối (câu 134, 138, 142, 146), nhưng có văn bản đặt ở blank 3. Để
    mô hình tự chọn thì nó rải lung tung hoặc bỏ hẳn, và mỗi câu riêng lẻ vẫn
    hợp lệ nên không cổng nào ở tầng câu thấy được.
    """
    plan = bp.build_part6("tp-test", "Test", seed=3)
    assert bp.validate(plan) == []
    where = []
    for slot in plan.parts[0].slots:
        at = [
            i for i, code in enumerate(slot.question_types) if code == "PART_6_SENTENCE_INSERTION"
        ]
        assert len(at) == 1 and at[0] in (2, 3)
        where.append(at[0])
    # Và CHIA ĐỀU hai vị trí ấy. Bản trước dồn 4·4·4·3, tức ba trên bốn cụm đặt ở
    # chỗ trống cuối — người luyện vài đề học được "chỗ trống cuối là câu điền"
    # mà không cần đọc, cùng loại manh mối với thiên lệch chữ cái đáp án.
    assert sorted(where) == [2, 2, 3, 3]
    # Đặt ở blank 1 (chưa đủ câu chữ xung quanh) là sai — cổng phải bắt được.
    plan.parts[0].slots[0].question_types[0] = "PART_6_SENTENCE_INSERTION"
    assert any("câu điền câu phải ở blank 3 hoặc 4" in problem for problem in bp.validate(plan))


def _slot_and_block(part: int):  # type: ignore[no-untyped-def]
    """Một ô và một khối dán hợp lệ cho part đó."""
    builders = {
        1: (bp.build_part1, PART1_GOOD),
        2: (bp.build_part2, PART2_GOOD),
        3: (bp.build_part3, PART3_GOOD),
        5: (bp.build_part5, GOOD),
        6: (bp.build_part6, PART6_GOOD),
    }
    builder, block = builders[part]
    plan = builder("tp-test", "Test", seed=7) if part != 5 else builder("tp-test", "Test", 7, 1)
    plan.parts[0].slots = plan.parts[0].slots[:1]
    slot = plan.parts[0].slots[0]
    if part == 1:
        block = block.replace("us_female_1", slot.voice)
    if part == 2:
        block = block.replace("us_female_1", slot.voices[0])
    return plan, slot, block


@pytest.mark.parametrize("part", [1, 2, 3, 5, 6])
def test_the_judge_always_receives_the_question_itself(part, tmp_path):
    """Yêu cầu gửi cho người chấm phải chứa được NỘI DUNG câu hỏi, ở mọi part.

    Đây là bài test đắt giá nhất của cả chặng kiểm, vì cùng một lỗi đã xảy ra BA
    lần và mỗi lần đều đọc ra như "nội dung kém":

      · Part 3 không được gửi lời thoại — 26 cờ giả trên 39 câu;
      · câu hỏi về hình không được gửi bảng — 3 cờ giả;
      · Part 2 không được gửi câu hỏi (nó nằm ở lượt nói đầu, `prompt_text` là
        NULL) — 15 cờ giả trên 25 câu, kèm hai cờ "có 4 phương án" cho câu chỉ
        có ba.

    Điểm chung: người chấm thiếu ngữ cảnh KHÔNG im lặng, nó trả về một chữ cái
    như thường. Dấu hiệu duy nhất là tỉ lệ cờ cao — thứ dễ đọc thành lỗi nội
    dung hơn là lỗi cổng kiểm.
    """
    plan, slot, block = _slot_and_block(part)
    writer.save_slot(tmp_path, slot, block)
    if part == 1:
        (tmp_path / "photos").mkdir(exist_ok=True)
        (tmp_path / "photos" / f"{slot.id}.txt").write_text("A photograph of one man at a desk.")

    recorder = _Recorder()
    checker.check_blueprint(plan, tmp_path, recorder, Tier.CHEAP, False, part)  # type: ignore[arg-type]
    assert recorder.seen, f"part {part}: chặng đối chiếu không gọi lượt nào"

    # Mỗi part giấu "câu hỏi" ở một chỗ khác nhau — đó chính là lý do lỗi này
    # lặp lại. Chỗ nào cũng phải tới được tay người chấm.
    needle = {
        1: "one man at a desk",  # mô tả ảnh
        2: "quarterly sales report",  # lượt nói đầu
        3: "interview schedule for tomorrow",  # lời thoại
        5: "expense reports",  # đề bài in ra
        6: "your subscription",  # ngữ liệu
    }[part]
    for request in recorder.seen:
        assert needle in request.user, f"part {part}: thiếu ngữ cảnh trong yêu cầu"


PART7_TWO = """[PASSAGE]
FOR IMMEDIATE RELEASE

Apex Electronics announces the SoundBar Pro, shipping December 1. Distributors
receive an initial allocation of 600 units.

[PASSAGE]
Dear Ms. Rossi,

Thank you for the launch notice. We request an additional 200 units to cover
confirmed dealer commitments.

Sincerely,
James Whitaker

[QUESTION]
What is the purpose of the first document?
(A) To announce a new product
(B) To confirm a refund
(C) To cancel an order
(D) To request a review
Answer: A
Source: original

[QUESTION]
How many extra units does Mr. Whitaker request?
(A) One hundred
(B) Two hundred
(C) Four hundred
(D) Six hundred
Answer: B
Source: original
"""

PART7_TRIPLE = """[PASSAGE]
Dear Member,

Please join us for the premiere on June 18. Fill out the order form below.

Sincerely,
Mariam Abdulla

[PASSAGE]
Show Date | Ticket Price
June 17 | twelve pounds
June 18 | eighteen pounds
June 19 | twenty pounds

[PASSAGE]
Name: Anil Bhatia
Performance date: June 18
Tickets: 2

[QUESTION]
What is the purpose of the letter?
(A) To invite a member to a premiere
(B) To confirm a refund
(C) To announce a closure
(D) To request a donation
Answer: A
Source: original

[QUESTION]
How much will Mr. Bhatia pay per ticket?
(A) Twelve pounds
(B) Eighteen pounds
(C) Twenty pounds
(D) Twenty-four pounds
Answer: B
Source: original
"""


def test_a_multi_passage_set_must_actually_have_its_passages(tmp_path):
    """Đếm ngữ liệu, không chỉ hỏi "có ngữ liệu không".

    Đo được: cả BA cụm ba-ngữ-liệu của lượt chạy đầu chỉ sinh ra MỘT khối
    `[PASSAGE]` — mô hình gộp cả ba tài liệu vào một đoạn. Parser nhận (1–3 đều
    hợp lệ), cổng cũ chỉ hỏi "có ngữ liệu không", nên nhóm bài đọc ba ngữ liệu
    lặng lẽ thành nhóm một ngữ liệu và mất đúng cái làm nên nhóm đó: câu hỏi
    phải vắt qua nhiều tài liệu.
    """
    # Cụm TOÀN CHỮ, không hình: bài này ghim phép đếm ngữ liệu, và một cụm có
    # hình sẽ đỏ vì thiếu hình chứ không vì thiếu đoạn văn — hai chuyện khác
    # nhau, và trộn lại thì không biết cổng nào vừa kêu.
    plan = bp.build_part7("tp-test", "Test", seed=3)
    slot = next(s for s in plan.parts[0].slots if len(s.passages) > 1 and not any(s.passages))
    slot.question_types = slot.question_types[:2]
    # Bài này ghim PHÉP ĐẾM NGỮ LIỆU, không phải trục độ khó — xem `_graphic_plan`.
    slot.hard = 0
    plan.parts[0].slots = [slot]

    writer.save_slot(tmp_path, slot, PART7_TWO)
    assert all(r.problems == [] for r in checker.check_blueprint(plan, tmp_path, only=7))

    # Gộp ba tài liệu vào một khối: vẫn là văn bản hợp lệ, và phải bị chặn.
    merged = PART7_TWO.replace("\n[PASSAGE]\nDear Ms. Rossi", "\nDear Ms. Rossi")
    writer.save_slot(tmp_path, slot, merged)
    problems = [p for r in checker.check_blueprint(plan, tmp_path, only=7) for p in r.problems]
    assert any("cần 2 ngữ liệu" in problem for problem in problems)


def test_part_7_special_forms_must_point_at_something_real(tmp_path):
    """Ba dạng câu của Part 7 hỏng theo cùng một kiểu: câu đọc trôi chảy, có
    đúng một đáp án, và thứ nó trỏ tới KHÔNG có trong ngữ liệu. Người học đi tìm
    một chỗ không tồn tại rồi kết luận là mình đọc sót.
    """
    plan = bp.build_part7("tp-test", "Test", seed=3)
    slot = next(s for s in plan.parts[0].slots if len(s.passages) == 3)
    slot.question_types = slot.question_types[:2]

    # từ vựng: hỏi một từ không có trong bài
    vocab = PART7_TRIPLE.replace(
        "How much will Mr. Bhatia pay per ticket?",
        'In the letter, the word "subsequent" in paragraph 1 is closest in meaning to',
    )
    assert any(
        "xuất hiện 0 lần" in p
        for p in checker.check_part7_forms(*_parsed(vocab, len(slot.question_types)))
    )

    # điền câu: ngữ liệu không có dấu [1]–[4]
    insert = PART7_TRIPLE.replace(
        "How much will Mr. Bhatia pay per ticket?",
        "In which of the positions marked [1], [2], [3], and [4] does the "
        "following sentence best belong?",
    )
    assert any(
        "thiếu dấu" in p
        for p in checker.check_part7_forms(*_parsed(insert, len(slot.question_types)))
    )

    # hàm ý: lời trích không có trong bài
    quote = PART7_TRIPLE.replace(
        "How much will Mr. Bhatia pay per ticket?",
        'At 9:26 A.M., what does Ms. Lee mean when she writes, "I am on it"?',
    )
    assert any(
        "không có trong ngữ liệu" in p
        for p in checker.check_part7_forms(*_parsed(quote, len(slot.question_types)))
    )


def _parsed(block: str, wanted: int):  # type: ignore[no-untyped-def]
    questions, passages, _ = checker.parse_group(block, 7, wanted)
    return questions, passages


def test_the_brief_prompt_states_each_kind_s_answer_axis():
    """Lời nhắc sinh brief phải nói trục đáp án của TỪNG dạng, không chỉ của `table`.

    Đây là lỗi thật, tìm ra khi chạy đồ thị bằng Kimi: lời nhắc cũ chỉ nêu một ví
    dụ và là `table` ("cột Gói và Phí"), nên model suy rộng mẫu hai cột sang
    `schedule` và sinh brief "cột Thời gian và Hoạt động". Người viết đề làm ĐÚNG
    brief đó rồi bị `answer_axis()` chặn — với schedule, trục là tiêu đề CỘT, nên
    bảng hai cột chỉ còn một mục thay vì bốn. Ba vòng đều hỏng cùng chỗ.

    Đổi model không cứu được: hai lời nhắc phải nói cùng một điều, và đó là lý do
    `AXIS_BRIEF` sống cạnh chính `answer_axis()`.
    """
    from app.content.exam.graphics import AXIS_BRIEF
    from app.content.exam_cli.plan import generate_part_graphics

    recorder = _Recorder()
    try:
        generate_part_graphics(recorder, None, 3, ["A", "B", "C"])
    except Exception:
        # Gateway giả trả "A", không phải brief hợp lệ — nó NÉM, đúng như tài
        # liệu của hàm. Thứ đang kiểm là lời nhắc đã gửi đi, không phải đầu ra.
        pass

    assert recorder.seen, "không có lượt gọi nào để kiểm"
    prompt = recorder.seen[0].system
    assert AXIS_BRIEF in prompt
    assert "TIÊU ĐỀ CỘT" in prompt
    assert 'bảng hai cột "Thời gian | Hoạt động"' in prompt


def test_the_brief_prompt_says_which_slot_each_graphic_lands_on():
    """Lượt sinh brief phải biết ô hình sắp rơi vào, không thì hình lạc chủ đề.

    Lỗi thật trên `tp-form-08`: `p3-13` mang `topic` nhà ở mà brief là phiếu khảo
    sát phòng gym, `p3-12` mang chủ đề sự kiện công ty mà brief là số khách bảo
    tàng. `topic` đến từ bảng `PART3_MIX`, brief đến từ một lượt gọi riêng, và
    hai bên chỉ được ghép bằng vị trí trong danh sách — nên `bp.validate` vẫn
    xanh và lỗi chỉ nổ ở người viết đề, người phải chèn một câu gượng để nhắc
    tới tấm hình.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam_cli.plan import _graphic_hosts, generate_part_graphics

    plan = bp.build_part3("s", "t", 20260822)
    hosts = _graphic_hosts(plan)
    with_graphic = [slot for slot in plan.parts[0].slots if slot.graphic]
    assert len(hosts) == len(with_graphic) == 3
    for host, slot in zip(hosts, with_graphic, strict=True):
        assert slot.topic in host, "bối cảnh phải là của đúng ô nhận hình"

    recorder = _Recorder()
    try:
        generate_part_graphics(recorder, None, 3, hosts)
    except Exception:
        pass
    prompt = recorder.seen[0].system
    for host in hosts:
        assert host in prompt


def test_the_graphic_rule_is_judged_not_guessed(tmp_path):
    """Luật hình được xét bằng PHÂN LOẠI, không bằng một lần đoán đáp án.

    Bản đầu bảo model tự trả lời câu hỏi khi giấu lời thoại: trúng thì kết luận
    "hình tự trả lời". Cách đó phụ thuộc một lần đoán — bốn lựa chọn thì đoán bừa
    trúng 1/4, và cả trúng lẫn trượt đều bị đọc thành kết luận. Bản này cho model
    đọc CẢ hình lẫn thoại kèm luật, rồi chỉ hỏi item rơi vào ô nào.

    Ba ca lỗi lấy từ `tp-form-08`: "Which phase is forty percent complete?" đọc
    thẳng khỏi biểu đồ (GRAPHIC_ONLY), và ô đạt là `p3-13` — thoại nói giá, bảng
    tra ra tên hàng.
    """
    from dataclasses import dataclass

    from app.content.exam.check import graphic_rule_verdict

    @dataclass
    class _Opt:
        label: str
        content: str
        is_correct: bool
        spoken_text: str = ""

    @dataclass
    class _Q:
        prompt_text: str
        options: list

    source = tmp_path / "p3-12.txt"
    source.write_text(
        "kind: chart\nImplementation Progress in percent\n"
        "Planning | 100\nDevelopment | 75\nTesting | 40\nDeployment | 15\n"
    )
    question = _Q(
        "Look at the graphic. Which phase is forty percent complete?",
        [
            _Opt("A", "Planning", False),
            _Opt("B", "Testing", True),
            _Opt("C", "Development", False),
            _Opt("D", "Deployment", False),
        ],
    )

    class _Says:
        def __init__(self, reply):
            self.reply = reply

        def run(self, request, feature, tier):  # noqa: ANN001, ARG002
            self.seen = request
            return _result(self.reply)

    def verdict_of(reply):
        return graphic_rule_verdict(_Says(reply), question, "kịch bản", source, tier=None)

    # Ba ô lỗi đều thành lời than CHẶN NẠP; `OK` thì không.
    for name in ("GRAPHIC_ONLY", "TALK_ONLY", "NEITHER"):
        verdict, complaint = verdict_of(name)
        assert verdict == name and complaint, name
    assert verdict_of("OK") == ("OK", None)
    # Phán quyết lạ KHÔNG được thành "đạt" — trả nguyên văn để caller ghi cờ.
    verdict, complaint = verdict_of("có lẽ ổn")
    assert verdict and verdict != "OK" and complaint is None

    # Lời thoại PHẢI được gửi đi: giấu nó thì model không xét được TALK_ONLY.
    gw = _Says("OK")
    graphic_rule_verdict(gw, question, "người phụ nữ nói bà lái xe cỡ lớn", source, tier=None)
    assert "xe cỡ lớn" in gw.seen.user


def test_the_paid_check_costs_one_slot_not_one_part(tmp_path, monkeypatch):
    """Lượt kiểm CÓ GỌI MODEL phải thu về đúng ô đang viết.

    Đồ thị gọi `check_blueprint` sau mỗi ô. Với `only=part`, ô thứ k kéo theo cả
    k ô đã viết trước nó, nên chi phí cộng dồn thành bình phương — đo được 8,2
    lần mức cần thiết trên một đề, riêng Part 5 là 15,5 lần. Tệ hơn tiền: một ô
    đã đạt bị chấm lại hàng chục lần và có thể "hỏng" vì nhiễu ở lượt kiểm của
    một ô khác.

    Số lượt gọi không hiện ra ở đâu cả — đề vẫn đúng, chỉ đắt và chậm — nên nó
    cần một phép đếm chứ không thể trông vào việc ai đó nhận ra.
    """
    from collections import Counter

    from app.content.exam import blueprint as bp
    from app.content.exam.check import check_blueprint

    plan = bp.build_part5("tp-test", "Test", seed=7)
    slots = plan.parts[0].slots[:4]
    plan.parts[0].slots = slots
    for slot in slots:
        writer.save_slot(tmp_path, slot, GOOD)

    class _Counting:
        def __init__(self):
            self.n = Counter()

        def run(self, request, feature, tier):  # noqa: ANN001, ARG002
            self.n[feature] += 1
            return _result("A")

    whole = _Counting()
    check_blueprint(plan, tmp_path, gateway=whole, ambiguity=True, only=5, quiet=True)
    one = _Counting()
    reports = check_blueprint(
        plan, tmp_path, gateway=one, ambiguity=True, only=5, quiet=True, slot_id=slots[2].id
    )

    assert [r.slot_id for r in reports] == [slots[2].id]
    # Bốn ô một câu: cả part tốn 8 lượt, một ô tốn 2. Đây là phép đếm, không
    # phải phép so "ít hơn" — "ít hơn" vẫn xanh khi lỗi bình phương quay lại.
    assert sum(whole.n.values()) == 8
    assert sum(one.n.values()) == 2


def test_each_slot_shape_gets_its_own_output_budget():
    """Trần đầu ra theo HÌNH DẠNG ô, không một con số cho cả trăm ô.

    Nội dung sinh ra chỉ 64–401 token, nên gần như toàn bộ trần là phần suy
    luận và nó tỉ lệ với ĐỘ KHÓ. Đo được: `p3-11` bị cắt ở trần 12 000, còn ô
    không hình dùng nhiều nhất 7 739.

    Và trần rộng không miễn phí — model nở suy luận cho vừa ngân sách: cùng một
    ô có hình, trần 40 000 mất 322 giây còn 25 000 chỉ mất 225.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam.writer import GRAPHIC_MAX_TOKENS, max_tokens_for

    part3 = bp.build_part3("s", "t", 20260822).parts[0].slots
    plain = next(s for s in part3 if not s.graphic)
    graphic = next(s for s in part3 if s.graphic)

    # Ô có hình phải rộng hơn hẳn: 12 000 đã từng CẮT một ô như thế.
    assert max_tokens_for(3, graphic) == GRAPHIC_MAX_TOKENS
    assert max_tokens_for(3, graphic) > 12000
    # Ô thường vẫn phải trên mức dùng nhiều nhất đã đo (7 739).
    assert max_tokens_for(3, plain) > 7739
    assert max_tokens_for(3, plain) < max_tokens_for(3, graphic)

    # Part 7 là ngoại lệ, và ngoại lệ ấy THẮNG: trần của nhà cung cấp (340 giây,
    # đo được) nhỏ hơn thứ một ô ba ngữ liệu muốn dùng, nên nó bị kẹp xuống dưới
    # ngưỡng đó chứ không được hưởng `GRAPHIC_MAX_TOKENS` như ô hình Part 3/4.
    from app.content.exam.writer import PART7_MAX_TOKENS

    part7 = bp.build_part7("s", "t", 20260822).parts[0].slots
    with_graphic = next(s for s in part7 if any(s.passages))
    assert max_tokens_for(7, with_graphic) == PART7_MAX_TOKENS
    assert PART7_MAX_TOKENS < GRAPHIC_MAX_TOKENS


def test_part_7_stays_under_the_provider_response_ceiling():
    """Trần của NHÀ CUNG CẤP thắng trần của ta, và Part 7 là chỗ chạm nó.

    Đo được ba lượt ngắt kết nối ở 340 154 / 340 144 / 340 465 ms — lệch 0,3
    giây trên 340, tức là một trần cố định chứ không phải mạng chập chờn. Nó cắt
    bất kể cửa sổ đọc của ta rộng bao nhiêu, nên trần SINH phải nằm dưới nó.

    Ranh giới trùng khít hình dạng ô: mười ô một ngữ liệu đạt hết, `p7-11` (hai
    ngữ liệu, năm câu) hỏng cả hai lần thử. Nội dung thật chỉ ~700 token, phần
    vượt trần là suy luận — nên hạ trần cắt đúng thứ đang thừa.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam.writer import PROVIDER_CEILING_TOKENS, max_tokens_for

    for slot in bp.build_part7("s", "t", 20260822).parts[0].slots:
        budget = max_tokens_for(7, slot)
        assert budget < PROVIDER_CEILING_TOKENS, f"{slot.id} vượt trần nhà cung cấp"
        # Đủ biên: sinh xong ở nhịp CHẬM vẫn phải kịp, không chỉ ở nhịp trung bình.
        assert budget <= 10000


def test_the_part_7_rule_says_how_to_build_a_cross_reference_not_just_to_have_one():
    """Luật "cần cả hai tài liệu" phải là CÁCH DỰNG, không phải lời khuyên.

    Bản cũ chỉ nói "ít nhất một câu phải cần cả hai", và model tuân thủ đúng chữ
    mà vi phạm trọn vẹn tinh thần: nó mở câu hỏi bằng "Based on the e-mail and
    the seating map…" trong khi email đã nói thẳng đáp án. Bốn ô Part 7 sinh
    thật đều hỏng như vậy.

    Ba thứ dưới đây là thứ bản cũ thiếu: một thủ tục dựng, một phép thử tự làm
    được, và các ca hỏng viết ra thành ví dụ — model bám ví dụ chặt hơn bám mô
    tả, và đây là ví dụ hỏng THẬT chứ không phải ví dụ bịa.
    """
    from app.content.exam.prompts import SYSTEM_PART7 as rule

    # Thủ tục: chia đôi thứ người đọc cần, mỗi tài liệu giữ một nửa.
    assert "HOW TO BUILD IT" in rule
    assert "DESCRIPTION" in rule and "maps that onto the ANSWER" in rule
    # Cấm chiều ngược lại, thứ bản cũ không nói: tài liệu B không được nhắc lại
    # luật của tài liệu A. Thiếu vế này thì hai tài liệu mã hoá cùng một quan hệ
    # và không câu hỏi nào có thể cần cả hai.
    assert "never restate" in rule

    # Phép thử che tay: kiểm được mà không cần gọi model.
    assert "cover one document" in rule.lower()

    # Và cái bẫy tinh vi nhất: câu hỏi mặc áo "Based on both" mà chỉ cần một.
    assert "Based on the e-mail and the schedule" in rule
    assert "is not what makes a question a" in rule


def test_every_set_part_hands_the_grader_its_source_material():
    """Người chấm phải ĐỌC ĐƯỢC thứ nó đang chấm — cả BỐN part dạng cụm.

    Cùng một lỗi đã xảy ra năm lần trong pipeline này, và lần nào cũng hỏng theo
    kiểu tệ nhất: người chấm mù vẫn trả về một chữ cái, nên phép kiểm TRÔNG như
    đang chạy. Part 7 là lần thứ năm — nó rơi xuống nhánh cuối của `_stem` và
    chỉ nhận đề bài trần, nên đo ngày 2026-08-31 cho ra 50 cờ trên 54 câu, phần
    lớn là "có 4 phương án điền được (ABCD)". Không cái nào là lỗi nội dung.

    Kiểm cả bốn part một lượt chứ không riêng Part 7: bài học của năm lần trước
    là part tiếp theo thêm vào cũng sẽ bị quên.
    """
    from app.content.exam.check import _stem

    class _Q:
        prompt_text = "What is the main purpose of the e-mail?"
        options: list = []
        script: list = []

    marker = "NGUYÊN VĂN NGỮ LIỆU"
    for part in (3, 4, 6, 7):
        assert marker in _stem(_Q(), part, marker), f"part {part}: người chấm không thấy ngữ liệu"


PART7_BLOCK = """[PASSAGE]
From: coordinator@example.test
To: guest@example.test
Subject: Seating

Dear Ms. Lee, your group has been assigned the table by the stage. Please
arrive by six o'clock so that the photographer can take a group portrait.

[QUESTION]
What is the purpose of the message?
(A) To give seating and arrival details
(B) To request a payment
(C) To cancel an event
(D) To offer a refund
Answer: A
Source: original
[QUESTION]
By what time should the guest arrive?
(A) Five o'clock
(B) Six o'clock
(C) Seven o'clock
(D) Eight o'clock
Answer: B
Source: original
[QUESTION]
What will happen before the event begins?
(A) A portrait will be taken.
(B) A meal will be served.
(C) A speech will be given.
(D) A prize will be awarded.
Answer: A
Source: original
[QUESTION]
Which zone is the group seated in?
(A) Zone A
(B) Zone B
(C) Zone C
(D) Zone D
Answer: B
Source: original
[QUESTION]
In the message, the word "assigned" is closest in meaning to
(A) given
(B) sold
(C) refused
(D) copied
Answer: A
Source: original
"""


def test_the_grader_of_a_part_7_set_can_read_its_graphics(tmp_path):
    """Hình Part 7 phải tới tay người chấm, không chỉ được ĐẾM.

    Lần thứ sáu của cùng một lỗi. Dòng nối hình vào `script` nằm trong nhánh
    `slot.graphic`, tức chỉ Part 3/4; hình Part 7 sống ở `slot.passages` nên
    khối của nó chỉ đếm tệp. Đo thật: sau khi cho người chấm đọc ngữ liệu văn
    xuôi, số cờ Part 7 sụt từ 50 xuống 6 — và cả 6 cờ còn lại đều rơi vào câu
    cần đọc HÌNH. Tương quan hoàn hảo đó là thứ chỉ ra chỗ hỏng còn lại.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam.check import _check_set

    plan = bp.build_part7("s", "t", 20260822)
    slot = next(s for s in plan.parts[0].slots if any(s.passages))
    (tmp_path / "graphics").mkdir()
    (tmp_path / "graphics" / f"{slot.id}.txt").write_text(
        "kind: map\nSƠ ĐỒ MỐC\nZone A: lối vào | Zone B: sân khấu\n"
    )

    seen_prompts: list[str] = []

    class _Recording:
        tally = type("T", (), {"line": lambda self: ""})()

        def run(self, request, feature, tier):  # noqa: ANN001, ARG002
            seen_prompts.append(request.user)
            return _result("A")

    _check_set(slot, PART7_BLOCK, 7, plan, _Recording(), None, False, {}, tmp_path)
    assert seen_prompts, "người chấm chưa được gọi lần nào"
    assert "SƠ ĐỒ MỐC" in seen_prompts[0], "người chấm không thấy hình"


def test_balance_counts_questions_per_slot_instead_of_multiplying(tmp_path):
    """Part 7 có số câu KHÁC NHAU từng ô, nên đích phải cộng dồn chứ không nhân.

    `QUESTIONS_PER_SET` không có hàng cho Part 7, nên `get(part, 1)` trả về 1 và
    mỗi ô chỉ nhận MỘT đích trong khi nó có tới năm câu. Bốn câu còn lại giữ
    nguyên chữ cái model tự chọn.

    Đo thật trên tp-form-08: sáu part khớp đích chính xác, riêng Part 7 ra
    A=24/54 (44%) so với đích A=13. Lệch đó không phép kiểm nào chặn — ngưỡng
    `check_answer_spread` tính trên CẢ đề nên 44% ở một part bị pha loãng thành
    30% và lọt qua.
    """
    from app.content.exam import blueprint as bp
    from app.content.exam.balance import letters_for, plan_targets
    from app.content.exam.blueprint import QUESTIONS_PER_SET

    slots = bp.build_part7("s", "t", 20260822).parts[0].slots
    counts = [len(s.question_types) or QUESTIONS_PER_SET.get(7, 1) for s in slots]

    # Nhân với hằng số cho 15 đích; cộng dồn cho 54 — đúng bằng số câu Part 7.
    assert len(slots) * QUESTIONS_PER_SET.get(7, 1) == 15
    assert sum(counts) == 54
    assert len(plan_targets(sum(counts), 20260822, letters_for(7))) == 54

    # Và các ô KHÔNG cùng số câu, thứ làm phép nhân sai ngay từ đầu.
    assert len(set(counts)) > 1


# --- Phân bố độ khó -------------------------------------------------------
#
# Mix quyết định đề khó hay dễ, và nó trôi bằng một dòng sửa mà không ai thấy.
# Ba bài dưới đây ghim đúng những con số mà `SPEC-EXAM-DIFFICULTY` lập luận.


def _question_types(rows, index: int) -> list[str]:
    return [code for row in rows for code in row[index]]


def test_part2_keeps_a_third_of_its_answers_indirect() -> None:
    """Trục độ khó lớn nhất của Part 2 là đáp án GIÁN TIẾP, không phải dạng câu.

    Bỏ cột này đi thì mọi câu là đáp thẳng — vẫn 25 câu Part 2 hợp lệ, vẫn phủ
    đủ mười dạng câu hỏi, và không phép kiểm nào khác thấy đề đã dễ đi.
    """
    from app.content.exam.mixes import PART2_MIX

    direct = sum(row[1] for row in PART2_MIX)
    indirect = sum(row[2] for row in PART2_MIX)
    assert direct + indirect == 25
    assert indirect == 8

    slots = bp.build_part2("x", "X", 7).parts[0].slots
    assert sum(slot.indirect for slot in slots) == 8
    # Rải khắp đề, không dồn về cuối: người làm gặp câu khó từ sớm.
    positions = [i for i, slot in enumerate(slots) if slot.indirect]
    assert min(positions) < 12 and max(positions) > 12


def test_every_listening_part_carries_its_implication_questions() -> None:
    """Câu hàm ý là dạng khó nhất của Part 3/4 và là dạng dễ vắng mặt nhất.

    Part 3 từng có **không câu nào** — mã `PART_3_IMPLICATION` chưa tồn tại
    trong taxonomy — nên cả part chỉ còn chủ đề, chi tiết và hành động tiếp
    theo, tức ba dạng dễ nhất. `SPEC-EXAM-DIFFICULTY` §10 D3 đo lại và thấy ba
    câu mỗi part vẫn quá thưa (8% số câu, và chỉ MỘT khuôn), nên mix nay rải hàm
    ý trên ~nửa số cụm.
    """
    from app.content.exam.mixes import PART3_MIX, PART4_MIX

    p3 = _question_types(PART3_MIX, 3)
    p4 = _question_types(PART4_MIX, 2)
    assert len(p3) == 39 and len(p4) == 30
    assert p3.count("PART_3_IMPLICATION") == 6
    assert p4.count("PART_4_IMPLICATION") == 6
    # Một cụm ba câu không được mang hai câu hàm ý — đề thật không làm thế, và
    # hai lời trích trong một hội thoại ngắn thì lời sau không còn hàm ý gì.
    for row in PART3_MIX:
        assert list(row[3]).count("PART_3_IMPLICATION") <= 1
    for row in PART4_MIX:
        assert list(row[2]).count("PART_4_IMPLICATION") <= 1


def test_listening_implications_span_all_four_forms() -> None:
    """Đủ số câu hàm ý là một nửa; nửa kia là chúng phải KHÁC khuôn.

    `*_IMPLICATION` chỉ có một shape trong system prompt, nên thêm ô mà không có
    `implication_kind` thì cả sáu câu cùng ra "What does she mean when she
    says…?" — y khuôn sụp-How mà `how_variant` đã phải sửa. `build_part3`/`4`
    quay vòng bốn biến thể TRÊN RIÊNG các cụm hàm ý, xáo theo seed.
    """
    from app.content.exam.prompts.difficulty import _IMPLICATION_VARIANTS

    n = len(_IMPLICATION_VARIANTS)
    for part, build in ((3, bp.build_part3), (4, bp.build_part4)):
        plan = build("tp-test", "Test", seed=7)
        kinds = [
            slot.implication_kind
            for slot in plan.parts[0].slots
            if any(code.endswith("_IMPLICATION") for code in slot.question_types)
        ]
        assert len(kinds) >= n, f"part {part} có {len(kinds)} cụm hàm ý, không đủ phủ {n} biến thể"
        assert set(kinds) == set(range(n)), f"part {part} không dùng đủ {n} biến thể: {kinds}"
        # Ô không hàm ý phải giữ kind 0 (mặc định), không ăn chỉ số của vòng quay.
        for slot in plan.parts[0].slots:
            if not any(code.endswith("_IMPLICATION") for code in slot.question_types):
                assert slot.implication_kind == 0


def test_an_old_blueprint_still_loads_with_implication_kind_zero(tmp_path) -> None:
    """Blueprint sinh trước khi có `implication_kind` phải nạp được nguyên vẹn.

    `QuestionSlot` thêm field mới với default 0, nên `load` một tệp cũ (thiếu
    khoá) giữ hành vi cũ — không phải migrate, và một đề đã duyệt không tự nhiên
    đổi biến thể hàm ý khi chạy lại chặng sinh.
    """
    plan = bp.build_part3("tp-old", "Old", seed=7)
    path = tmp_path / "blueprint.json"
    bp.save(plan, path)
    raw = json.loads(path.read_text())
    for part in raw["parts"]:
        for slot in part["slots"]:
            slot.pop("implication_kind", None)
    path.write_text(json.dumps(raw))
    restored = bp.load(path)
    assert all(slot.implication_kind == 0 for slot in restored.parts[0].slots)
    assert bp.validate(restored) == []


def test_part7_does_not_lean_on_its_two_easiest_question_types() -> None:
    """Tìm-thông-tin và chủ đề là hai dạng dễ nhất của Part 7.

    Chúng từng chiếm 27/54 câu — một nửa cả part. Đề thật nghiêng hẳn về suy
    luận; mức trần ở đây là thứ giữ cho nó không trôi ngược lại.
    """
    from app.content.exam.mixes import PART7_SETS

    codes = _question_types(PART7_SETS, 2)
    assert len(codes) == 54
    easy = codes.count("PART_7_INFORMATION_RETRIEVAL") + codes.count("PART_7_TOPIC_OR_PURPOSE")
    assert easy <= 20
    assert codes.count("PART_7_INFERENCE") >= 18
    # Đề thật có đúng hai câu điền câu và hai câu hàm ý (hai cụm tin nhắn).
    assert codes.count("PART_7_SENTENCE_INSERTION") == 2
    assert codes.count("PART_7_IMPLICATION") == 2


def test_an_implication_question_must_quote_the_script_word_for_word() -> None:
    """Bỏ lời trích đi thì còn lại một câu hỏi chi tiết hoàn toàn hợp lệ — và
    không có gì trong đầu ra nói cho ta biết ô này đã viết sai dạng."""
    from app.content.exam.check import check_implication
    from app.services.content_import import ParsedQuestion

    script = "M: I've already been to the warehouse.\nW: Then we can skip the second run."

    quoted = ParsedQuestion(
        line=1,
        prompt_text='What does the man mean when he says, "I\'ve already been to the warehouse"?',
    )
    assert check_implication(quoted, script) == []

    bare = ParsedQuestion(line=1, prompt_text="What did the man do this morning?")
    assert check_implication(bare, script)

    invented = ParsedQuestion(
        line=1, prompt_text='What does the man mean when he says, "I will call the supplier"?'
    )
    assert check_implication(invented, script)


# --- Chống trùng khung giữa các đề ---------------------------------------
#
# Năm đề đầu tiên đều mang seed `20260822` — mặc định ghi cứng của `--seed` —
# nên khung của chúng giống hệt nhau: cùng dãy dạng câu, cùng chủ đề cụm, cùng
# thứ tự bài. Nội dung thì khác thật (trùng từ vựng giữa các cụm khác đề đo được
# Jaccard trung vị 0,03–0,07), nhưng người làm hai đề vẫn gặp đúng một hình dạng
# đề: câu 32 luôn hỏi chủ đề, câu 34 luôn hỏi hành động tiếp theo.


def _skeleton(slug: str, seed: int) -> list[tuple]:
    builders = {
        1: bp.build_part1,
        2: bp.build_part2,
        3: bp.build_part3,
        4: bp.build_part4,
        5: bp.build_part5,
        6: bp.build_part6,
        7: bp.build_part7,
    }
    out = []
    for part, build in builders.items():
        for slot in build(slug, slug, seed).parts[0].slots:
            out.append(
                (
                    part,
                    slot.question_type,
                    tuple(slot.question_types),
                    slot.grammar,
                    tuple(slot.grammars),
                    slot.topic,
                    slot.people,
                    slot.context,
                    slot.graphic,
                    tuple(slot.passages),
                    slot.structure,
                )
            )
    return out


def test_two_forms_do_not_share_a_skeleton() -> None:
    """Hai đề khác tên phải khác khung, và điều đó không được phụ thuộc vào việc
    ai đó nhớ truyền `--seed`.

    Đo trước khi sửa: cùng seed mặc định thì hai blueprint trùng **99/99 ô**.
    """
    from app.content.exam_cli.plan import seed_for

    a = _skeleton("tp-form-11", seed_for("tp-form-11"))
    b = _skeleton("tp-form-12", seed_for("tp-form-12"))
    same = sum(1 for x, y in zip(a, b) if x == y)
    assert same < len(a) * 0.25, f"{same}/{len(a)} ô trùng — khung hai đề quá giống nhau"


def test_the_same_slug_still_rebuilds_the_same_form() -> None:
    """Suy seed từ slug không được lấy mất tính tái lập.

    `hash()` của Python ngẫu nhiên hoá theo tiến trình, nên dùng nó ở đây thì
    dựng lại cùng một slug ở lần chạy sau ra một đề khác — bài này là chỗ điều
    đó bị bắt.
    """
    from app.content.exam_cli.plan import seed_for

    assert seed_for("tp-form-11") == seed_for("tp-form-11")
    assert _skeleton("tp-form-11", seed_for("tp-form-11")) == _skeleton(
        "tp-form-11", seed_for("tp-form-11")
    )


@pytest.mark.parametrize(
    ("part", "build", "at"),
    [(3, bp.build_part3, (10, 11, 12)), (4, bp.build_part4, (8, 9))],
)
def test_the_graphic_sets_stay_at_the_end_however_the_mix_is_shuffled(part, build, at) -> None:
    """Câu hỏi về hình nằm ở CUỐI part, ở mọi đề thật.

    `build_part3` gán brief cho ô 10–12 và `build_part4` cho ô 8–9 theo VỊ TRÍ,
    nên xáo cả bảng sẽ đẩy một hàng vốn có hình lên đầu và đẻ ra câu hỏi hình ở
    giữa part. Từng câu vẫn hợp lệ, nên không có gì báo.
    """
    for seed in (1, 20260822, 987654321):
        slots = build("x", "X", seed).parts[0].slots
        assert tuple(i for i, s in enumerate(slots) if s.graphic) == at


def test_part7_keeps_single_then_double_then_triple() -> None:
    """Đề thật xếp cụm một đoạn trước, rồi hai đoạn, rồi ba.

    `number` cộng dồn theo số câu của ô trước, nên trộn một cụm 5 câu vào giữa
    đám cụm 2 câu vẫn đánh số liền mạch tới 200 — không có gì báo, chỉ là đề
    không còn giống đề thi.
    """
    for seed in (1, 20260822, 987654321):
        slots = bp.build_part7("x", "X", seed).parts[0].slots
        counts = [len(s.passages) for s in slots]
        assert counts == sorted(counts), f"seed {seed}: thứ tự đoạn {counts}"
        assert slots[0].number == 147
        assert slots[-1].number + len(slots[-1].question_types) - 1 == 200


# --- Đáp án nhiễu phải nhại lời thoại ------------------------------------
#
# Bẫy trung tâm của Part 3/4 đề thật: đáp án SAI mới là chỗ dùng lại từ của lời
# thoại rồi bẻ nghĩa. Đề tự sinh làm ngược — đo trên 276 câu của bốn đề đầu, 58%
# đáp án ĐÚNG nhại gần hết lời thoại còn 37% đáp án nhiễu không nhắc tới gì, nên
# "chọn cái nghe quen nhất" đúng 46–49% số câu thay vì 25%.


def _mc(script: str, correct: str, wrong: list[str]):
    from app.services.content_import import ParsedOption, ParsedQuestion

    return ParsedQuestion(
        line=1,
        prompt_text="What will the man do next?",
        options=[ParsedOption(label="A", content=correct, is_correct=True)]
        + [
            ParsedOption(label=chr(66 + i), content=w, is_correct=False)
            for i, w in enumerate(wrong)
        ],
    )


SHIFT_SCRIPT = (
    "W: The delivery van is scheduled for Thursday morning. "
    "M: Actually we moved it to Friday, and I will email the warehouse manager today."
)


def test_two_unrelated_distractors_are_refused() -> None:
    """Ba đáp án sai không nhắc tới gì thì đáp án đúng là lựa chọn DUY NHẤT chứa
    từ nào của lời thoại — một điểm cho không với người bắt được một từ."""
    from app.content.exam.check import check_distractors

    lazy = _mc(
        SHIFT_SCRIPT,
        "Email the warehouse manager",
        ["Repaint the lobby", "Cancel a magazine subscription", "Book a dentist appointment"],
    )
    assert check_distractors(lazy, SHIFT_SCRIPT)


def test_distractors_that_echo_the_script_pass() -> None:
    """Kế hoạch bị đổi, người nói khác, quan hệ bị bẻ — cả ba đều dùng lại từ đã
    nói. Đây là hình dạng đề thật dùng."""
    from app.content.exam.check import check_distractors

    good = _mc(
        SHIFT_SCRIPT,
        "Email the warehouse manager",
        [
            "Send the van on Thursday morning",  # kế hoạch cũ, đã bị đổi
            "Ask the warehouse manager to email him",  # bẻ quan hệ
            "Reschedule the delivery for next week",  # nghe quen, không ai nói
        ],
    )
    assert check_distractors(good, SHIFT_SCRIPT) == []


def test_a_correct_answer_may_still_echo_the_script() -> None:
    """KHÔNG chặn đáp án đúng nhại lời thoại.

    Đề thật có những câu trả lời được bằng cách khớp cụm từ; bỏ chúng đi làm đề
    KHÓ hơn đề thật, sai theo hướng ngược lại. Cổng này chỉ canh sàn của đáp án
    nhiễu, nên một đáp án đúng lấy nguyên chữ vẫn phải qua.
    """
    from app.content.exam.check import check_distractors, echo

    item = _mc(
        SHIFT_SCRIPT,
        "Email the warehouse manager",
        [
            "Send the van on Thursday morning",
            "Ask the warehouse manager to email him",
            "Meet the delivery van on Friday",
        ],
    )
    assert echo("Email the warehouse manager", SHIFT_SCRIPT) == 1.0
    assert check_distractors(item, SHIFT_SCRIPT) == []


# --- Bốn luật của CỤM (guide §10, §26, §27–28) ---------------------------


GYM_TALK = (
    "The new City Fitness Center opens on Saturday at the old market square. "
    "Every membership plan is fifty percent off for the first three months. "
    "That includes personal training, group classes, and pool access. "
    "The offer ends next Friday, so please visit the front desk before closing."
)


def _q(stem: str, correct: str, wrong: list[str]):
    from app.services.content_import import ParsedOption, ParsedQuestion

    return ParsedQuestion(
        line=1,
        prompt_text=stem,
        options=[ParsedOption(label="A", content=correct, is_correct=True)]
        + [
            ParsedOption(label=chr(66 + i), content=w, is_correct=False)
            for i, w in enumerate(wrong)
        ],
    )


def test_a_question_may_not_name_another_answer_in_the_same_set() -> None:
    """Guide §27–28. Đây là lỗi ĐÃ xảy ra, gần nguyên ví dụ của tài liệu: câu 1
    có nhiễu "To explain how to use the pool access" trong khi đáp án câu 2 là
    "Personal training, group classes, and pool access" — đọc câu 1 là gặp trước
    từ vựng của đáp án câu 2. Đo trên 30 câu Part 4: 23% dính lỗi này."""
    from app.content.exam.check import check_leakage

    leaky = [
        _q("What is the purpose?", "To announce a discount", ["To explain the pool access"]),
        _q("What is included?", "Personal training and pool access", ["A free towel"]),
    ]
    assert check_leakage(leaky)

    clean = [
        _q("What is the purpose?", "To announce a discount", ["To explain a refund policy"]),
        _q("What is included?", "Personal training and pool access", ["A free towel"]),
    ]
    assert check_leakage(clean) == []

    # Chỉ những từ RIÊNG của đáp án đúng mới rò rỉ. `p4-03` bị báo oan vì
    # "eleven fifteen" — cụm ấy nằm ở ba trên bốn lựa chọn của câu bên cạnh, nên
    # gặp trước nó không tách được đáp án đúng khỏi nhiễu.
    spread = [
        _q(
            "What is the new boarding time?",
            "Thirty minutes after eleven fifteen",
            ["At eleven fifteen", "Twenty-two minutes after eleven fifteen", "At noon"],
        ),
        _q(
            "What will happen after the weather clears?",
            "Passengers receive seat information by text",
            [
                "Passengers board at eleven fifteen",
                "Passengers wait beside the desk",
                "Passengers collect vouchers",
            ],
        ),
    ]
    assert check_leakage(spread) == []


def test_two_questions_on_the_same_sentence_are_one_question_twice() -> None:
    """Guide §27. Đề bài khác nhau không cứu được: người làm trả lời câu thứ hai
    bằng đúng thao tác vừa dùng cho câu thứ nhất."""
    from app.content.exam.check import check_redundancy

    same = [
        _q("What is included?", "Personal training and group classes", ["A towel"]),
        _q("What does the plan cover?", "Group classes and pool access", ["Parking"]),
    ]
    assert check_redundancy(same, GYM_TALK)

    apart = [
        _q("What is included?", "Personal training and group classes", ["A towel"]),
        _q("When does the offer end?", "Next Friday", ["On Saturday"]),
    ]
    assert check_redundancy(apart, GYM_TALK) == []


def test_a_set_answerable_from_single_sentences_is_flagged_not_blocked() -> None:
    """Guide §10 (D1) và §23: độ khó đáng ngờ là REVIEW, không phải REJECT.

    Phép đo là xấp xỉ theo từ chung — một đáp án diễn đạt lại giỏi có thể chạm
    ít câu mà vẫn khó — nên chặn nạp bằng nó là cách chắc chắn để không ai chạy
    cổng nữa. Đo được: 63% câu Part 4 vừa sinh nằm gọn trong một câu, và nhóm
    "ghép từ ba chỗ" tụt 20% → 7% sau khi thêm luật cân bằng độ trùng chữ.
    """
    from app.content.exam.check import check_retrieval_spread

    local = [
        _q("When does the offer end?", "Next Friday", ["On Saturday"]),
        _q("Where is the centre?", "At the old market square", ["At the front desk"]),
    ]
    assert check_retrieval_spread(local, GYM_TALK)

    spread = [
        _q("When does the offer end?", "Next Friday", ["On Saturday"]),
        _q(
            "What must a member do to get the discount?",
            "Visit the front desk before Friday to start a membership plan",
            ["Pay online after Saturday"],
        ),
    ]
    assert check_retrieval_spread(spread, GYM_TALK) == []


CROSS_SET = """[PASSAGE]
MEMO
The spring supplier fair opens on March 9 at the Halden Centre.
Booth fees are due one week before the fair.

[PASSAGE]
Dear Ms. Ito,
Your booth fee of four hundred dollars was received on March 1.
Thank you for registering early.

[QUESTION]
Was the booth fee paid on time?
(A) Yes, it arrived before the deadline
(B) No, it arrived after the fair
(C) The fee was waived
(D) The fee is still outstanding
Answer: A
Explanation: {evidence} | (A) đúng. | (B) sai. | (C) sai. | (D) sai.
Source: original
"""


def test_a_graphic_set_is_exempt_from_the_combining_requirement(tmp_path):
    """Ở cụm có hình, câu hỏi về hình CHÍNH LÀ câu ghép hai nguồn.

    Thoại cấp một toạ độ NGOÀI trục đáp án, hình tra toạ độ ấy ra đáp án — dạng
    khó nhất của cụm. Nhưng phép đếm câu văn không nhìn thấy nó: lời thoại cố ý
    không đọc tên hàng, nên đáp án chỉ khớp phần BẢNG được ghép vào `script`.

    Đo trên `p3-13`: bỏ câu hỏi về hình ra thì còn hai câu, cả hai span 1, và
    cổng đòi thêm một câu ghép nữa — tức bắt cụm ba câu mang HAI câu khó, thứ đề
    thật không làm.
    """
    plan = _graphic_plan(tmp_path)
    slot = plan.parts[0].slots[0]
    assert slot.graphic, "fixture phải là ô có hình"
    slot.hard = 1

    reports = checker.check_blueprint(plan, tmp_path, only=3)
    assert all("ghép hai chỗ tách rời" not in problem for r in reports for problem in r.problems)


def test_a_yes_no_decoy_is_a_trap_until_most_questions_use_it(tmp_path):
    """Bẫy thật của đề thật, nhưng ở tần suất cao nó thôi là bẫy và thành một luật.

    Đo trên `tp-form-11`: **11/15** câu WH (73%) có một nhiễu mở đầu bằng "Yes",
    loại được từ chữ đầu tiên. Người làm khi đó chỉ còn chọn giữa hai phương án,
    và đáp án gián tiếp — trục độ khó lớn nhất của Part 2 — không bao giờ được
    kiểm, vì loại trừ đưa tới nó trước khi phải hiểu lời né.

    Lỗi ở tầng ĐỀ: từng câu hoàn toàn hợp lệ, y như thiên lệch chữ cái đáp án.
    """
    plan = bp.build_part2("tp-test", "Test", seed=7)
    wh = [
        s
        for s in plan.parts[0].slots
        if any(code in s.question_type for code in ("_WHO_", "_WHERE_", "_WHEN_", "_WHY_"))
    ][:12]
    plan.parts[0].slots = wh

    def paste(question: str, decoy: str) -> str:
        return (
            f"[QUESTION]\nvoice: us_female_1\n{question}\nvoice: us_male_1\n"
            f"(A) On the second floor.\n(B) {decoy}\n(C) At nine tomorrow.\n"
            "Answer: A\nSource: original\n"
        )

    for slot in wh:
        writer.save_slot(tmp_path, slot, paste("Where is the report?", "Yes, I sent it."))
    problems = checker.check_yes_no_spread(tmp_path, plan)
    assert any("nhiễu Yes/No" in problem for problem in problems)
    # Gọi tên phần VƯỢT hạn ngạch, không phải tất cả — bẫy này hợp lệ, thứ phải
    # sinh lại là số dôi ra. Cắt theo thứ tự id để `prune` không đuổi theo một
    # đích di động giữa hai lần chạy trên cùng nội dung.
    named = [word for word in problems[0].split() if word.startswith("p2-")]
    assert len(named) == len(wh) - int(len(wh) * checker.YES_NO_DECOY_LIMIT)
    assert named == sorted(named)

    # Một vài câu dùng nó thì vẫn là bẫy, không phải luật.
    for index, slot in enumerate(wh):
        decoy = "Yes, I sent it." if index < 2 else "The printer is broken."
        writer.save_slot(tmp_path, slot, paste("Where is the report?", decoy))
    assert checker.check_yes_no_spread(tmp_path, plan) == []


def test_a_part_6_explanation_may_quote_the_blank_filled_in() -> None:
    """Ngữ liệu Part 6 MANG chỗ trống trong chính nó, nên lời giải trích câu "đã
    điền" không bao giờ khớp ngữ liệu thô — mà đoạn ấy bắt buộc phải có: không
    cho người học thấy kết quả điền thì lời giải không giải thích gì cả.

    Đo được: cả bốn ô Part 6 của `tp-form-11` mang một cờ giả, và bốn ô ấy hoàn
    toàn sạch. Cờ giả theo cấu tạo còn tệ hơn không có cờ — nó dạy người duyệt bỏ
    qua cờ.
    """
    from app.content.exam.check import _filled_passage

    passage = "All requests ------- (1) online. The work may ------- (2) postponed."
    qs = [
        _q("Blank (1)", "are submitted", ["submit"]),
        _q("Blank (2)", "be", ["been"]),
    ]
    filled = _filled_passage(passage, qs)
    assert "All requests are submitted online." in filled
    assert "may be postponed" in filled
    # Mỗi đáp án vào ĐÚNG chỗ trống mang số của nó, không phải chỗ trống kế tiếp.
    assert "-------" not in filled


def test_a_part_7_implication_question_quotes_with_writes_not_says() -> None:
    """Part 3/4 NÓI, Part 7 VIẾT — và cụm tin nhắn là chỗ duy nhất dạng câu hàm ý
    sống được ở phần Đọc, nên đề thật viết *"what does Mr. X mean when he writes"*.

    Bản chỉ bắt `says` chặn oan **100%** câu hàm ý Part 7 — hai ô mỗi đề, và cả
    hai trích dẫn hoàn toàn đúng. Không có bài này thì triệu chứng đọc như "mô
    hình không viết nổi câu hàm ý", đúng kiểu quy oan cho model mà một cổng chặt
    hơn prompt luôn tạo ra.
    """
    from app.content.exam.check import check_implication

    script = "Nolan Reyes [9:40 A.M.]\nI'll have the warehouse layout ready by then."
    written = _q(
        "At 9:40 A.M., what does Mr. Reyes mean when he writes, "
        '"I\'ll have the warehouse layout ready by then"?',
        "He will finish it before the Friday briefing",
        ["He will ask someone else to prepare it"],
    )
    assert check_implication(written, script) == []

    # Vẫn bắt đúng hai lỗi cũ: không trích, và trích một câu không có thật.
    bare = _q("What does Mr. Reyes plan to do?", "Finish the layout", ["Cancel the meeting"])
    assert check_implication(bare, script)
    invented = _q(
        'What does Mr. Reyes mean when he writes, "the depot closes at noon"?',
        "The depot shuts early",
        ["The depot stays open"],
    )
    assert check_implication(invented, script)


def test_a_multi_passage_set_needs_one_explanation_citing_both_documents() -> None:
    """Câu bắc cầu là LÝ DO cụm nhiều tài liệu tồn tại — không có nó thì ba tài
    liệu chỉ là ba cụm một tài liệu in cạnh nhau.

    Đo bằng TRÍCH DẪN chứ không bằng từ chung, vì `check_retrieval_spread` im ở
    **69%** cụm Part 7: đáp án Part 7 phần lớn là số tính ra, câu NOT, hoặc suy
    luận — cả ba đều vô hình với phép đếm từ chung. Trích dẫn thì nguyên văn theo
    hợp đồng và biên giới khối thì biết chính xác, nên phép đo là tra bảng.
    """
    from app.content.exam.check import check_cross_passage, parse_group

    one_side = CROSS_SET.format(
        evidence='Thông báo ghi "Booth fees are due one week before the fair"'
    )
    qs, _, _ = parse_group(one_side, 7, 1, 2)
    assert check_cross_passage(qs, one_side)

    both = CROSS_SET.format(
        evidence='Thông báo ghi "the spring supplier fair opens on March 9" và hạn nộp là '
        'trước đó một tuần; thư xác nhận "was received on March 1"'
    )
    qs, _, _ = parse_group(both, 7, 1, 2)
    assert check_cross_passage(qs, both) == []


def test_an_unmeasurable_answer_makes_the_spread_gate_abstain() -> None:
    """Đáp án là con số tính ra, hoặc câu NOT — cả hai cho span 0 một cách hợp lệ.

    Lời phàn nàn của cổng là "KHÔNG câu nào trong cụm phải ghép hai chỗ", và muốn
    khẳng định thế thì phải đo được mọi câu. `_content_words` chỉ bắt `[a-z]+`
    nên "¥18,700" tách ra rỗng, còn đáp án của câu NOT thì theo định nghĩa không
    có trong ngữ liệu. Đo trên `p7-01`: câu tính giá đúng là câu ghép mà prompt
    yêu cầu, và cổng vẫn chặn cả cụm vì không nhìn thấy nó.
    """
    from app.content.exam.check import check_retrieval_spread

    local = [
        _q("When does the offer end?", "Next Friday", ["On Saturday"]),
        _q("Where is the centre?", "At the old market square", ["At the front desk"]),
    ]
    assert check_retrieval_spread(local, GYM_TALK)

    # Cùng cụm ấy, thêm một câu có đáp án KHÔNG đo được → cổng phải im.
    priced = [*local, _q("How much is the plan?", "$1,250", ["$900"])]
    assert check_retrieval_spread(priced, GYM_TALK) == []


def test_an_answer_that_shares_nothing_with_the_source_is_flagged() -> None:
    """Guide §26 Failure 5 — mặt còn lại của `check_paraphrase_balance`.

    "Transmit a lexical token through a mobile communication service" cho
    *"Text the word OPEN"* là lỗi riêng của nó. Cờ chứ không chặn: độ phủ thấp
    nói đáp án dùng chữ khác, KHÔNG chứng minh nó không tự nhiên.
    """
    from app.content.exam.check import check_thin_paraphrase

    thin = _q("What is included?", "Ancillary wellness provisions", ["A towel"])
    assert check_thin_paraphrase(thin, GYM_TALK)

    plain = _q("What is included?", "Group classes and pool access", ["A towel"])
    assert check_thin_paraphrase(plain, GYM_TALK) == []


def test_purpose_and_implication_do_not_count_toward_the_balance_gate() -> None:
    """`p4-06` rớt cổng này hai lượt sinh liên tiếp dù cụm đúng hình dạng prompt
    đòi — một câu khớp cụm từ (phủ 1.00), một câu mục đích (0.25), một câu hàm ý
    (0.40). Đáp án của mục đích và hàm ý là khái niệm bao trùm chứ không phải một
    lời đã nói, nên chúng KHÔNG THỂ có phủ cao; đếm chúng là phạt cụm vì nó khó,
    và đó là ràng buộc không thoả được. Cùng lý do câu hỏi về hình được miễn khỏi
    `check_distractors`."""
    from app.content.exam.check import check_paraphrase_balance

    trio = [
        _q(
            "What is the purpose of the announcement?",
            "To announce a promotion",
            [
                "To describe the training classes",
                "To open the market square",
                "To sell membership plans",
            ],
        ),
        _q(
            'What does the speaker mean when she says, "before closing"?',
            "Sign up soon to save money",
            [
                "Personal training is free",
                "The pool access ends Friday",
                "Group classes start Saturday",
            ],
        ),
        _q(
            "What is included in the plan?",
            "Personal training, group classes, and pool access",
            [
                "Membership plans and parking",
                "The front desk and the square",
                "Three months of classes",
            ],
        ),
    ]
    assert check_paraphrase_balance(trio, GYM_TALK)

    kinds = ["PART_4_TOPIC_OR_PURPOSE", "PART_4_IMPLICATION", "PART_4_DETAIL"]
    assert check_paraphrase_balance(trio, GYM_TALK, kinds) == []

    # Miễn theo MÃ, không phải miễn cả cụm: hai câu truy hồi cùng chạm đáy vẫn chặn.
    retrieval = ["PART_4_DETAIL", "PART_4_DETAIL", "PART_4_FUTURE_ACTION"]
    assert check_paraphrase_balance(trio, GYM_TALK, retrieval)
