"""Lời thoại -> nhãn người nói, dùng chung giữa khu luyện thi và luyện theo part."""

from app.schemas.practice import TranscriptTurn


def speaker_labels(script: list[dict[str, str]]) -> dict[str, str]:
    """Tên giọng logic -> nhãn để hiện, theo thứ tự XUẤT HIỆN trong lời thoại.

    `uk_female_1` là quy ước của phía offline và vô nghĩa với người học. Giới
    tính suy từ đoạn giữa; đánh số chỉ khi có TỪ HAI giọng cùng giới trong một
    lời thoại, vì "Man 1" khi chỉ có một người đàn ông đọc ra như thiếu mất
    người thứ hai.
    """
    order: list[str] = []
    for turn in script:
        voice = str(turn.get("voice", ""))
        if voice and voice not in order:
            order.append(voice)
    by_gender: dict[str, list[str]] = {}
    for voice in order:
        parts = voice.split("_")
        gender = "Woman" if len(parts) > 1 and parts[1] == "female" else "Man"
        by_gender.setdefault(gender, []).append(voice)
    labels: dict[str, str] = {}
    for gender, voices in by_gender.items():
        for index, voice in enumerate(voices, start=1):
            labels[voice] = gender if len(voices) == 1 else f"{gender} {index}"
    return labels


def transcript_of(script: list[dict[str, str]] | None) -> list[TranscriptTurn]:
    if not script:
        return []
    labels = speaker_labels(script)
    return [
        TranscriptTurn(
            speaker=labels.get(str(turn.get("voice", "")), "Speaker"),
            text=str(turn.get("text", "")),
        )
        for turn in script
        if turn.get("text")
    ]
