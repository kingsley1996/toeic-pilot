# Âm thanh

Cùng kỷ luật với `public/pet/CREDITS.md`: câu hỏi "tệp này ở đâu ra, có được
dùng không" phải trả lời được cho **từng tệp**, giống như `question.source`
không có giá trị mặc định.

| Tệp | Dùng ở đâu | Nguồn | Giấy phép |
|---|---|---|---|
| `petland.mp3` | nhạc nền góc thú cưng (`lib/petland-music.ts`) | [lofi hip hop](https://opengameart.org/content/lofi-hip-hop) — omfgdude, OpenGameArt | **CC0 1.0** (miền công cộng) |
| `complete.mp3` | tiếng báo khi làm xong một việc (`lib/sound.ts`) | **chưa ghi lại** | **chưa ghi lại** |

## `petland.mp3` ĐÃ BỊ SỬA, và sửa gì thì ghi ở đây

Khác hoàn toàn với tấm ghép ô, nơi `public/pet/CREDITS.md` khẳng định "không sửa
pixel nào". Bản gốc `lofihiphop.ogg` **không lặp được**: đo bằng `volumedetect`
thì một giây cuối ở **−62,7 dB** trong khi một giây đầu ở **−27,1 dB** — tức là
bài tắt dần xuống gần im lặng, và lặp thẳng sẽ nghe rõ một quãng lịm đi rồi bật
lại sau mỗi hai phút rưỡi.

Ba bước, đều đo được:

1. Cắt bỏ đoạn tắt dần. Nó bắt đầu ở giây **143** (từ −22 dB ở 142s xuống −39,8
   dB ở 144s).
2. Khâu vòng lặp: hai giây cuối `acrossfade` chồng lên hai giây đầu, rồi ghép
   phần thân phía sau. Nhờ vậy điểm nối cuối→đầu là một chuyển tiếp liên tục
   chứ không phải một vết cắt.
3. Xuất MP3 112 kbps mono (bản gốc vốn đã mono). MP3 chứ không giữ OGG vì Safari
   cũ không phát OGG, và `complete.mp3` cạnh nó cũng là MP3.

Kết quả đo lại: hai đầu còn chênh **5,7 dB** thay vì 35,6 dB. Dài 141 giây,
1,97 MB.

**Tôi không nghe được bản này** — mọi khẳng định ở trên là số đo, không phải cảm
nhận. Nghe thấy chỗ nối vẫn gợn thì chỉnh `X` (độ dài crossfade) hoặc đổi bài;
CC0 nên sửa thoải mái.

## `complete.mp3` có tệp mà không có xuất xứ

Tệp này được thêm vào trước khi có bảng này, và `public/pet/CREDITS.md` lại dẫn
chiếu tới đây như một kỷ luật đã có — nên khoảng trống này vốn vô hình. Viết ra
để nó thôi vô hình. Ai biết nguồn thì điền; không truy được thì cách sạch nhất
là thay bằng một tệp CC0 có nguồn rõ ràng.
