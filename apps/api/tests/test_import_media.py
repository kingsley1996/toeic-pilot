"""Phần khớp file với ô của trình nhập media hàng loạt.

Chỉ kiểm phần thuần: chọn số nào từ tên file, và báo cáo thừa/thiếu ra sao. Việc
tải lên và ghi hàng đã có đường riêng đi qua driver thật.
"""

from pathlib import Path

from app.content.import_media import Slot, collect, leading_number, match_files


def slot(number: int, part: int = 3) -> Slot:
    return Slot(number=number, part=part, label=f"câu {number}", owner=None, filled=False)  # type: ignore[arg-type]


def test_the_first_number_wins_not_the_last() -> None:
    """`32-34.mp3` là cụm MỞ ĐẦU ở câu 32.

    Lấy số cuối sẽ cho 34, và 34 không phải số mở đầu của cụm nào — nên mọi file
    Part 3/4 đặt tên theo khoảng sẽ trượt hết.
    """
    assert leading_number(Path("32-34.mp3")) == 32
    assert leading_number(Path("32_34.mp3")) == 32
    assert leading_number(Path("hoi-thoai.mp3")) is None


def test_a_part_label_in_the_filename_is_not_read_as_a_question_number() -> None:
    """`part3_32.mp3` phải là câu 32, không phải câu 3.

    Đây là hỏng IM LẶNG chứ không phải trượt: Part 1 chạy từ câu 1 đến 6, nên
    `3` khớp thành công vào một câu ảnh Part 1 và đoạn hội thoại Part 3 được gắn
    vào đó mà không có gì báo.
    """
    assert leading_number(Path("part3_32.mp3")) == 32
    assert leading_number(Path("Part_4-71.mp3")) == 71
    assert leading_number(Path("p2_07.mp3")) == 7
    # Không có số câu thì phải là None, chứ không phải số của nhãn part.
    assert leading_number(Path("part3.mp3")) is None


def test_unmatched_files_and_empty_slots_are_both_reported() -> None:
    """Không bỏ qua im lặng bên nào.

    Nhập một nửa để lại một đề thiếu đúng vài bản thu, và chỗ thiếu chỉ lộ ra
    khi có người ngồi làm tới đúng câu đó.
    """
    files = [Path("32.mp3"), Path("99.mp3")]
    slots = [slot(32), slot(35)]

    pairs, extra, empty = match_files(files, slots, "number")

    assert [(p.name, s.number) for p, s in pairs] == [("32.mp3", 32)]
    assert [p.name for p in extra] == ["99.mp3"]
    assert [s.number for s in empty] == [35]


def test_order_mode_zips_and_reports_the_leftovers() -> None:
    files = [Path("a.mp3"), Path("b.mp3"), Path("c.mp3")]
    slots = [slot(32), slot(35)]

    pairs, extra, empty = match_files(files, slots, "order")

    assert [(p.name, s.number) for p, s in pairs] == [("a.mp3", 32), ("b.mp3", 35)]
    assert [p.name for p in extra] == ["c.mp3"]
    assert empty == []


def test_files_sort_numerically_not_lexicographically(tmp_path: Path) -> None:
    """`1, 2, … 10` — không phải `1, 10, 11, 2`.

    Chế độ `index`/`order` ghép file với ô theo đúng thứ tự này, nên một lần
    `sorted()` mặc định là mười ba đoạn hội thoại vào sai chỗ, tất cả vẫn báo
    khớp thành công.
    """
    for name in ("1_a.mp3", "2_b.mp3", "10_c.mp3", "13_d.mp3"):
        (tmp_path / name).touch()

    assert [p.name for p in collect(tmp_path, {".mp3"})] == [
        "1_a.mp3",
        "2_b.mp3",
        "10_c.mp3",
        "13_d.mp3",
    ]


def test_index_mode_maps_position_in_the_part_not_the_question_number() -> None:
    """File thứ 10 của Part 2 là câu 16, không phải câu 10.

    `number` không chỉ trượt ở đây — nó khớp SAI, vì câu 10 cũng là một câu Part
    2 có thật. Khớp sai mà vẫn báo thành công là hỏng tệ hơn không khớp.
    """
    # Cả 25 ô của Part 2 — tra theo vị trí thì danh sách ô phải đầy đủ, đúng như
    # lúc chạy thật.
    slots = [slot(7 + i, part=2) for i in range(25)]
    files = [Path("8_x.mp3"), Path("9_y.mp3"), Path("10_z.mp3")]

    pairs, extra, empty = match_files(files, slots, "index")

    assert [(p.name, s.number) for p, s in pairs] == [
        ("8_x.mp3", 14),
        ("9_y.mp3", 15),
        ("10_z.mp3", 16),
    ]
    assert not extra
    assert len(empty) == 22


def test_index_mode_looks_up_by_position_so_gaps_do_not_shift_everything() -> None:
    """Chỉ vài cụm cuối Part 3/4 có hình, và chỗ trống không được đẩy phần còn lại.

    Ghép theo cặp (`zip`) sẽ đưa hình của cụm 11 vào cụm 1 — khớp thành công,
    không có gì báo, và người học thấy sơ đồ mặt bằng ở một đoạn hội thoại không
    nhắc tới nó.
    """
    files = [Path("11_a.webp"), Path("12_b.webp"), Path("13_c.webp")]
    slots = [slot(32 + 3 * i) for i in range(13)]

    pairs, extra, empty = match_files(files, slots, "index")

    assert [(p.name, s.number) for p, s in pairs] == [
        ("11_a.webp", 62),
        ("12_b.webp", 65),
        ("13_c.webp", 68),
    ]
    assert not extra
    assert len(empty) == 10


def test_an_index_past_the_end_is_reported_not_silently_dropped() -> None:
    files = [Path("14_x.webp")]
    pairs, extra, empty = match_files(files, [slot(32), slot(35)], "index")

    assert not pairs
    assert [p.name for p in extra] == ["14_x.webp"]
    assert len(empty) == 2


def test_a_filled_slot_does_not_shift_the_index_of_the_ones_after_it() -> None:
    """Chạy lại sau một lần nhập dở phải khớp y như lần đầu.

    Lọc ô đã đầy TRƯỚC khi khớp làm `index` sai: chỉ số tra theo vị trí, nên
    một ô bị rút khỏi danh sách đẩy mọi ô sau nó lên một bậc và `2_x.mp3` rơi
    vào ô thứ ba. Khớp thành công, không báo gì — mà chạy lại là đúng việc tài
    liệu bảo người ta làm.
    """
    slots = [slot(1, part=1), slot(2, part=1), slot(3, part=1)]
    slots[0].filled = True

    pairs, extra, empty = match_files([Path("2_x.webp")], slots, "index")

    assert [(p.name, s.number) for p, s in pairs] == [("2_x.webp", 2)]
    assert not extra
