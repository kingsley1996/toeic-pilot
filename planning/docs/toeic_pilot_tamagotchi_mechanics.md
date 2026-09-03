# Cơ chế trò chơi nuôi thú ảo kiểu Tamagotchi

## 1. Tổng quan

Cơ chế Tamagotchi có thể hiểu theo vòng lặp:

> **Pet có nhu cầu → người chơi chăm sóc → pet phát triển/thay đổi trạng thái → người chơi nhận phần thưởng → mở khóa nội dung mới → tiếp tục chăm sóc.**

Pet không chỉ là avatar trang trí. Pet có trạng thái sống, nhu cầu và phản ứng với hành động của người chơi.

### Core loop

```text
                 ┌──────────────┐
                 │   PET LIFE   │
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
       Hunger       Happiness      Hygiene
          │             │             │
          └─────────────┼─────────────┘
                        ↓
                Player takes care
                        ↓
              Stats / relationship
                        ↓
                  Pet grows up
                        ↓
                Evolution / death
```

---

## 2. Các chỉ số của pet

Một pet thường có một số stat thay đổi theo thời gian.

### Hunger

Ví dụ:

```text
Hunger: ❤️❤️❤️❤️♡
```

Theo thời gian hunger giảm. Người chơi phải cho pet ăn.

Nếu bỏ đói quá lâu:

```text
Hunger ↓
Happiness ↓
Health ↓
```

### Happiness

Pet có mức độ vui vẻ.

Ví dụ:

```text
Happiness: 72 / 100
```

Happiness có thể tăng bằng:

- Chơi
- Cho ăn món yêu thích
- Hoàn thành hoạt động
- Chăm sóc
- Tương tác với pet

Happiness thấp có thể khiến pet:

- Buồn
- Ít hoạt động
- Thay đổi animation
- Phát ra notification

### Hygiene

Pet có thể bị bẩn.

Ví dụ:

```text
Cleanliness: 30 / 100
```

Người chơi cần vệ sinh pet.

Nếu bỏ mặc:

```text
Dirty → Sick → Health ↓
```

### Health

Health thường là hệ quả của nhiều yếu tố:

```text
Health =
    Hunger
  + Hygiene
  + Sleep
  + Care
  + Random events
```

Health thấp có thể khiến pet bị bệnh.

---

## 3. Time-based simulation

Đây là phần rất quan trọng của Tamagotchi.

Pet tiếp tục tồn tại ngay cả khi người chơi không mở game.

Ví dụ:

```text
10:00
Hunger = 80

12:00
Hunger = 65

15:00
Hunger = 45

18:00
Hunger = 25
```

Khi user mở game lại:

```text
Last active: 10:00
Current: 18:00

Elapsed = 8 hours

→ calculate state changes
```

Không nhất thiết phải chạy server mỗi phút.

Có thể tính theo:

```ts
elapsedTime = now - lastUpdatedAt
```

Sau đó cập nhật trạng thái.

Đây là cơ chế rất phù hợp cho web/mobile game.

---

## 4. Needs decay

Có thể thiết kế mỗi stat với tốc độ giảm khác nhau.

Ví dụ:

```text
Hunger:
-2 / hour

Happiness:
-1 / hour

Energy:
-3 / hour

Hygiene:
-1 / hour
```

Sau 5 giờ:

```text
Hunger    -10
Happiness -5
Energy    -15
Hygiene   -5
```

Không nên để mọi thứ giảm tuyến tính mãi mãi.

Có thể dùng threshold:

```text
80–100   Healthy
60–79    Good
30–59    Needs attention
10–29    Critical
0–9      Emergency
```

---

## 5. Người chơi chăm sóc pet

Đây là interaction layer.

Ví dụ:

```text
🍎 Feed
🎮 Play
🧼 Clean
😴 Sleep
💊 Heal
❤️ Pet
```

Mỗi action ảnh hưởng tới một hoặc nhiều stat.

### Feed

```text
Hunger +25
Happiness +5
```

### Play

```text
Happiness +20
Energy -10
```

### Clean

```text
Hygiene +30
Happiness +5
```

### Sleep

```text
Energy +40
```

---

## 6. Không nên cho người chơi spam action

Đây là một mechanic quan trọng.

Ví dụ:

```text
Feed
↓
Cooldown 30 minutes
```

Hoặc:

```text
Feed capacity = 100

Hunger = 80
Feed +25

→ Hunger = 100
→ remaining food wasted
```

Như vậy người chơi phải quản lý pet thay vì spam button.

---

## 7. Growth / Life stages

Một trong những mechanic thú vị nhất của Tamagotchi là pet lớn lên.

Ví dụ:

```text
Egg
 ↓
Baby
 ↓
Child
 ↓
Teen
 ↓
Adult
 ↓
Special / Rare
```

Mỗi stage có:

- Sprite khác
- Animation khác
- Nhu cầu khác
- Personality khác
- Evolution path khác

Ví dụ:

```text
Egg
  ↓
Baby Dragon
  ↓
Young Dragon
  ↓
Fire Dragon
```

Hoặc:

```text
Baby
 ↓
Good care
 ↓
Angel Pet

Baby
 ↓
Poor care
 ↓
Lazy Pet
```

---

## 8. Evolution không chỉ dựa vào level

Đây là mechanic rất hay để tạo replayability.

Evolution có thể phụ thuộc vào:

```text
Care Score
Happiness
Health
Study Activity
Number of mistakes
Consistency
```

Ví dụ:

```text
Care Score > 90
→ Golden Dragon

Care Score 70–89
→ Normal Dragon

Care Score 40–69
→ Sleepy Dragon

Care Score < 40
→ Grumpy Dragon
```

Người chơi không nhất thiết biết chính xác pet sẽ tiến hóa thành gì.

Điều này tạo cảm giác:

> "Lần này mình sẽ nuôi được con gì?"

---

## 9. Personality

Pet có thể có personality.

Ví dụ:

```text
🐉 Brave
🐱 Curious
🐰 Lazy
🦊 Clever
🐻 Friendly
```

Personality ảnh hưởng animation và reaction.

### Curious

```text
User mở bài học
→ pet chạy lại
→ "What's this?"
```

### Lazy

```text
User không chăm sóc
→ pet ngủ
```

### Energetic

```text
Happiness > 80
→ pet chạy quanh màn hình
```

---

## 10. Discipline / behavior

Tamagotchi truyền thống còn có khái niệm behavior/discipline.

Ví dụ pet:

```text
🍎 Hungry
😴 Sleepy
💩 Dirty
😢 Sad
```

Nếu người chơi chăm sóc đúng cách:

```text
Care ↑
Discipline ↑
```

Nếu bỏ bê:

```text
Care ↓
Discipline ↓
```

Trong game hiện đại có thể chuyển thành:

> **Relationship / Bond**

thay vì "discipline".

---

## 11. Bond / Relationship

Đây là mechanic rất phù hợp với TOEIC Pilot.

Ví dụ:

```text
Bond Level

Lv 1  Stranger
Lv 2  Friend
Lv 3  Companion
Lv 4  Best Friend
Lv 5  Soulmate
```

Bond tăng khi:

- Học mỗi ngày
- Hoàn thành lesson
- Chăm pet
- Chơi mini-game
- Duy trì streak

Pet có thể mở dialogue mới theo bond.

Ví dụ:

```text
Bond Lv 1

"Hi..."

Bond Lv 3

"You're back! Let's study together!"

Bond Lv 5

"I knew you could do it!"
```

---

## 12. Death / failure

Tamagotchi nguyên bản có mechanic chết.

Pet bị ảnh hưởng bởi việc người chơi bỏ bê.

Ví dụ:

```text
Hunger = 0
Health = 0
Too long
   ↓
Pet dies
```

Tuy nhiên, với TOEIC Pilot không nên dùng death theo kiểu nghiêm khắc.

Không nên:

```text
Không học 3 ngày → pet chết
```

Nên thay bằng:

```text
Neglect
 ↓
Pet becomes sad
 ↓
Stats decrease
 ↓
Pet asks for attention
```

Sau đó người chơi có thể recover.

---

## 13. Random events

Random event làm pet có cảm giác "sống".

Ví dụ:

```text
🎁 Pet found a mysterious egg!

🌧️ Pet doesn't like today's weather.

🍪 Pet found a cookie.

😴 Pet fell asleep.

✨ Pet discovered something!
```

Random event có thể phụ thuộc vào:

```text
time
weather
streak
level
pet type
user activity
```

---

## 14. Rewards

Người chơi cần được thưởng khi chăm pet.

Ví dụ:

```text
Complete lesson
      ↓
+10 XP
+5 Ruby
+1 Bond
```

Sau đó:

```text
Ruby
 ↓
Egg
 ↓
New Pet
```

Đây chính là meta progression.

---

## 15. Collection system

Game có thể có hệ thống collection.

Ví dụ:

```text
Pets
├── Common
├── Uncommon
├── Rare
├── Epic
└── Legendary
```

Người chơi có mục tiêu:

```text
Collection: 12 / 50
```

Pet đã unlock được lưu vào:

```text
Pet Collection
```

Sau đó user có thể đổi pet active.

---

## 16. Items

Có thể có inventory:

```text
Inventory

🍎 Apple × 12
🍰 Cake × 3
🎾 Ball × 5
🧸 Toy × 2
🥕 Carrot × 8
```

Items có effect.

Ví dụ:

```text
Apple
Hunger +15

Cake
Hunger +30
Happiness +20

Ball
Happiness +25
Energy -10
```

---

## 17. Currency

Có thể có ít nhất 2 loại currency.

### Soft currency

Ví dụ:

```text
🪙 Coins
```

Nhận từ:

- Học
- Daily quest
- Mini-game

Dùng để:

- Mua food
- Mua toy
- Trang trí

### Premium / special currency

Ví dụ:

```text
💎 Ruby
```

Dùng để:

- Mở egg
- Unlock rare pet
- Cosmetic

Trong TOEIC Pilot, **Ruby** phù hợp với concept phần thưởng.

---

## 18. Daily quest

Đây là cách kết nối game với learning loop.

Ví dụ:

```text
Today's Missions

☐ Complete 10 vocabulary questions
☐ Finish 1 dictation
☐ Study for 15 minutes
☐ Feed your pet
```

Reward:

```text
+50 XP
+20 Ruby
+1 Bond
```

Game không cạnh tranh với việc học.

**Game trở thành incentive cho việc học.**

---

## 19. Streak

Ví dụ:

```text
🔥 Study Streak: 12 days
```

Mỗi ngày học:

```text
Streak +1
```

Pet cũng phản ánh streak:

```text
3 days
→ pet gets excited

7 days
→ unlock accessory

14 days
→ rare egg

30 days
→ special evolution
```

---

## 20. Offline / Away state

Một vấn đề quan trọng với virtual pet là user không thể mở app liên tục.

Vì vậy nên có:

```text
last_simulated_at
```

Ví dụ:

```text
last_simulated_at:
2026-09-03 10:00

user returns:
2026-09-03 18:00
```

Backend tính:

```text
8 hours elapsed
```

Sau đó simulate:

```text
Hunger -16
Energy -24
Happiness -8
```

Nên có giới hạn:

```text
max simulation = 24h
```

để pet không bị trạng thái quá tệ khi user nghỉ vài ngày.

---

## 21. Notification

Pet có thể gọi người chơi quay lại.

Ví dụ:

```text
🐉 "I'm getting hungry..."

🐉 "Let's study together!"

🐉 "I found something!"

🐉 "I miss you!"
```

Notification nên được dùng vừa phải, tránh gây phiền.

---

## 22. Animation / visual feedback

Một phần quan trọng của Tamagotchi là pet phản ứng ngay lập tức.

### Người chơi làm đúng bài

```text
Question correct
      ↓
Pet jumps
      ↓
✨ sparkle
      ↓
+XP
```

### Người chơi làm sai

Không nên:

```text
😡 WRONG!
```

Nên:

```text
Pet looks curious
"Let's try again!"
```

### Hoàn thành lesson

```text
🎉
Pet celebrates
+20 XP
+5 Ruby
Bond +1
```

Visual feedback làm game có cảm giác "alive".

---

# 23. Hệ thống hoàn chỉnh

Nếu gom tất cả lại:

```text
                    PLAYER
                       │
                       ↓
                ┌─────────────┐
                │   LEARNING  │
                └──────┬──────┘
                       │
             XP / Ruby / Bond
                       │
                       ↓
                ┌─────────────┐
                │    PET      │
                └──────┬──────┘
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
     Hunger        Happiness       Energy
        │              │              │
        └──────────────┼──────────────┘
                       ↓
                  PET STATE
                       │
              ┌────────┴────────┐
              ↓                 ↓
          Growth             Events
              │                 │
              ↓                 ↓
         Evolution          Rewards
              │                 │
              └────────┬────────┘
                       ↓
                 COLLECTION
                       │
                       ↓
                  MORE PETS
                       │
                       └──────────→ LOOP
```

---

# 24. Áp dụng cho TOEIC Pilot

Không nên copy nguyên Tamagotchi.

Thay vào đó nên biến nó thành:

> **Learn → Care → Grow → Collect**

Ví dụ một ngày:

```text
09:00
User mở TOEIC Pilot

🐉 Pet:
"Good morning!"

User làm:
10 vocabulary questions
      ↓
+20 XP
+10 Ruby
+5 Bond

Pet:
🎉 Happy!

User làm:
1 dictation
      ↓
+30 XP

Pet:
✨ grows slightly

Cuối ngày:

Daily Goal: 100%
      ↓
🎁 Pet reward
      ↓
Egg fragment × 1
```

Sau 7 ngày:

```text
Study streak = 7
      ↓
Egg completed
      ↓
🥚 Hatch Egg
      ↓
🐲 New Pet!
```

Đây là một game loop phù hợp với app học TOEIC vì người dùng không cần chơi một game tách biệt. **Hành động học tập chính là hành động nuôi pet.**

---

# 25. Kiến trúc mechanic đề xuất cho TOEIC Pilot

```text
Learning
   │
   ├── XP ──────────→ Player Level
   │
   ├── Ruby ────────→ Eggs / Items
   │
   ├── Streak ──────→ Special Rewards
   │
   └── Accuracy ────→ Pet Evolution
                         │
                         ↓
                      New Pet
                         │
                         ↓
                    Collection
```

## Nguyên tắc thiết kế quan trọng

1. **Pet không nên trở thành một game độc lập.**
2. **Learning là core activity.**
3. **Pet là lớp gamification nằm trên learning system.**
4. Người học càng đều → pet càng khỏe, vui và phát triển.
5. Hành vi học tập nên tạo ra XP, Ruby, Bond và tiến trình evolution.
6. Không nên phạt người dùng quá nặng khi họ nghỉ học.
7. Ưu tiên positive reinforcement thay vì punishment.
8. Animation và reaction tức thời giúp tạo cảm giác pet "sống".
9. Collection và evolution tạo mục tiêu dài hạn.
10. Daily quest và streak tạo động lực quay lại mỗi ngày.

### Tổng kết vòng lặp

```text
        STUDY
          ↓
       REWARD
          ↓
      CARE PET
          ↓
      BOND / XP
          ↓
       PET GROWS
          ↓
      EVOLUTION
          ↓
    NEW PET / ITEM
          ↓
      COLLECTION
          ↓
      MORE STUDY
          │
          └──────────────→ LOOP
```

Mục tiêu cuối cùng của hệ thống là tạo ra cảm giác:

> **"Mình học để pet của mình lớn lên."**

Thay vì:

> **"Mình phải chơi game để nhận thưởng học tập."**
