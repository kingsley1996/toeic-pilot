# ĐÁNH GIÁ VỀ TÍNH NĂNG & GIAO DIỆN NUÔI PET TRONG ỨNG DỤNG TOEIC PILOT

---

##  EXECUTIVE SUMMARY
Tính năng nuôi Pet (Gamification) là một giải pháp hữu hiệu nhằm tăng **Tỷ lệ giữ chân người dùng (Retention Rate)** và **Thời lượng sử dụng ứng dụng (Engagement/Session Time)**. Tuy nhiên, qua phân tích thực tế từ giao diện ứng dụng **TOEIC Pilot**, mô hình hiện tại đang gặp một số xung đột nghiêm trọng giữa **Tính năng Game** và **Nhiệm vụ Học tập cốt lõi**.

Tài liệu này tổng hợp đánh giá chi tiết, phân tích rủi ro UX/Product và đề xuất lộ trình cải tiến cụ thể.

---

## 1. PHÂN TÍCH & ĐÁNH GIÁ CHI TIẾT (CURRENT STATE)

### 1.1. Điểm mạnh (Pros)
* **Visual độc đáo, tạo cảm giác nostalgic:** Phong cách Đồ họa Pixel Art (2D Pixel RPG) mang lại cảm giác thân thuộc (tương tự *Stardew Valley* hoặc *Pokémon*), giúp giao diện học tập trở nên bớt khô khan.
* **Cơ chế chỉ số rõ ràng:** Thiết lập các chỉ số sinh tồn (*No*, *Sức*, *Vui*) và giới hạn XP daily (*30 XP/ngày*) giúp định hình khung phát triển cho Pet.

### 1.2. Hạn chế & Rủi ro UX/Product (Cons & Friction Points)

#### 🛑 Rủi ro 1: Pop-up đè màn hình làm bài (Overlapping UI & High Cognitive Overload)
* **Thực trạng:** Giao diện Pet hiển thị dưới dạng một pop-up/cửa sổ nổi đè trực tiếp lên khu vực làm bài Dictation (Nghe chép chính tả).
* **Tác động:** 
  * Che mất khu vực `textarea` nhập đáp án và một phần trình phát Audio.
  * Việc một mini-game pixel màu sắc với hoạt ảnh chuyển động liên tục nằm ở góc màn hình gây phân tâm thị giác (Visual Distraction), làm giảm hiệu suất tiếp thu bài học nghe/hiểu.

#### 🛑 Rủi ro 2: Giới hạn XP chặn hành vi học tập (Counter-productive Game Economy)
* **Thực trạng:** Thông báo *"Hôm nay thú cưng đã nhận đủ 30 XP. Chăm tiếp vẫn có tác dụng, chỉ có điểm là dừng tới ngày mai"*.
* **Tác động:** Việc chặn nhận XP tạo cảm giác "hết nhiệm vụ" cho người dùng. Nếu động lực chính của học viên là cày level cho Pet, họ sẽ dừng học ngay khi đạt mốc 30 XP thay vì tiếp tục làm thêm bài tập.

#### 🛑 Rủi ro 3: Tương tác Game tách rời mục đích học (Disconnected Core Loop)
* **Thực trạng:** Các nút hành động (*Cho ăn*, *Chọc*, *Đi dạo*, *Ngủ*) mang tính bấm-là-xong (Instant Click).
* **Tác động:** Người dùng coi đây là một mini-game giải trí thuần túy thay vì là một động lực thôi thúc họ ôn tập từ vựng hay làm bài test.

---

## 2. ĐỀ XUẤT GIẢI PHÁP & TỐI ƯU CẤU TRÚC (PROPOSED ARCHITECTURE)

### 2.1. Tái cấu trúc Bố cục Giao diện (Layout Restructuring)

| Màn hình / Ngữ cảnh | Trạng thái hiển thị Pet | Mục đích UX |
| :--- | :--- | :--- |
| **Đang làm bài (In-session: Dictation, Test, Reading)** | **Ẩn hoàn toàn (Hidden)** | Dành $100\%$ diện tích và sự tập trung cho bài học. Không có vệt đè hay hạt màu phân tâm. |
| **Sidebar Menu chính (Fixed Left Bar)** | **Pet Compact Widget** | Hiển thị dạng thẻ thu nhỏ ($240 \times 120\text{px}$) gồm Avatar Pet, Level, và 2 thanh trạng thái đơn giản. |
| **Sau khi Nộp bài / Hoàn thành Unit** | **Floating Feedback/Toast** | Pet xuất hiện $2\text{s}$ nhảy múa kèm popup: `+5 XP 🐶` hoặc một câu khen ngợi bằng Tiếng Anh. |
| **Nhấp vào "Vào nhà Pet"** | **Full-screen Modal / Page** | Mở ra bản đồ Pixel RPG đầy đủ để người dùng chăm sóc, mua sắm đồ, xem tiến hóa. |

### 2.2. Tối ưu Game Economy & Vòng lặp Học tập (Core Loop Alignment)

1. **Thay thế "Giới hạn Hard-cap XP" bằng "Giảm dần hiệu suất (Diminishing Returns)":**
   * 3 bài test đầu tiên trong ngày: nhận $100\%$ XP ($10\text{ XP / bài}$).
   * Từ bài test thứ 4 trở đi: nhận $20\%$ XP ($2\text{ XP / bài}$).
   * *Mục tiêu:* Không bao giờ triệt tiêu động lực học thêm của học viên.

2. **Gắn liền Hành động Pet với Task Học tập:**
   * **Cho ăn:** Cần $10\text{ Coins}$ (Thu được khi trả lời đúng $10$ câu Part 5).
   * **Đi dạo:** Kích hoạt bài Flashcard ôn tập nhanh $5$ từ vựng trên đường đi.
   * **Chữa bệnh/Sức:** Phục hồi khi hoàn thành bài Mini-Test cuối ngày.

3. **Tiếng Anh hóa Giao diện Pet (Bilingual/English Immersion):**
   * Chuyển toàn bộ thoại và trạng thái của Pet sang Tiếng Anh chuẩn TOEIC.
   * *Ví dụ:* Thay vì *"Đang kiệt sức"*, hiển thị *"Exhausted! Complete 1 test to recharge me!"*.

---

## 3. CHECKLIST ĐÁNH GIÁ (PRODUCT SUMMARY)

* [x] **Trải nghiệm Học tập:** Cần ưu tiên làm sạch màn hình bài tập trước tiên.
* [x] **Thiết kế Widget:** Chuyển Pet về dạng Compact Widget ở Sidebar/Dashboard.
* [x] **Vòng lặp Động lực:** Học tập $ightarrow$ Nhận Coin/XP $ightarrow$ Nuôi Pet/Trang trí $ightarrow$ Khung tiến hóa gắn liền Target điểm TOEIC (450, 650, 800+).

---
*Bản đánh giá được tổng hợp dành cho dự án TOEIC Pilot.*
