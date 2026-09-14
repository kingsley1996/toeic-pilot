# ruff: noqa: E501, E702
"""Answer + Explanation cho P7 của tp-2024-NN (idempotent, dẫn xuất — sách không in key phần đọc).

    uv run python scripts/add_explanations_p7.py content/generated/tp-2024-01/paste
"""
import sys
from pathlib import Path

D = "(đáp án dẫn xuất từ ngữ cảnh — sách không in key phần Reading) "
E7 = {
"p7-01": [("C", """Câu hỏi dạng nguồn tài liệu. Passage là hướng dẫn "STOP! PLEASE READ FIRST" cho việc unpacking và lắp ráp → tờ giấy NHỒI trong hộp sản phẩm. | (A) "On a door" — không có ngữ cảnh cửa. | (B) "On a receipt" — hoá đơn không hướng dẫn lắp. | (C) "In a box" — đúng: lắp ráp khi vừa mua, trên thùng rỗng ép phẳng. | (D) "On a Web site" — Web chỉ được nhắc để đăng ký bảo hành."""),
 ("B", """Chi tiết suy luận loại đồ vật: "overtighten any screws or bolts… damage the wood or cushioning" — ốc vít + gỗ + đệm mút. | (A) "A desktop computer" — không lắp bằng ốc gỗ. | (B) "A piece of furniture" — đúng, gỗ + cushioning + lắp tại nhà. | (C) "A household appliance" — thiết bị điện không mô tả. | (D) "A power tool" — ngược, dụng cụ là đồ để lắp."""),
],
"p7-02": [("B", """Suy luận từ bảng: cột giờ Winnipeg song song cột giờ Toulouse (+6 tiếng) → một công ty có hai văn phòng ở hai múi giờ. | (A) "A conference" — lịch là meeting nội bộ, không có hội nghị. | (B) "A firm has offices in two time zones" — đúng. | (C) "Administrative assistants" — không nhắc tới ai đặt lịch cụ thể. | (D) "Some meeting times have been changed" — không có dấu hiệu thay đổi."""),
 ("C", """Câu chi tiết: passage yêu cầu xếp giờ "after 7:00 A.M. but before 11:00 A.M." (giờ Winnipeg). | (A) đóng cửa trưa — sai. | (B) Toulouse bắt đầu ngày — không phải ý của 11:00 Winnipeg. | (C) "It is not a preferred time to schedule a meeting" — đúng, vì chỉ "before" 11:00 mới được ưu tiên. | (D) "just been added" — không có."""),
],
"p7-03": [("B", """Câu chi tiết: "Built in 1897, it was the home of the Francona Charitable Trust until its renovation just over a year ago." | (A) bờ hồ — sai, cạnh vườn thực vật và sông. | (B) "It has recently been renovated" — đúng, cải tạo cách đây hơn một năm. | (C) sẽ xây vườn — sai, vườn đã có sẵn. | (D) chỉ cho sự kiện công ty — sai, cả cưới và hội thảo."""),
 ("D", """Suy luận: "Area residents know to plan far in advance to get a seat" → nhà hàng Andito's rất đông khách địa phương. | (A) đầu bếp quốc tế — chef Michaela Rymond không được mô tả quốc tịch. | (B) menu hạn chế — ngược, "meets all dietary needs". | (C) được tài trợ từ thiện — Trust chỉ từng sở hữu toà nhà. | (D) "very popular with local residents" — đúng."""),
],
"p7-04": [("A", """Trắc nghiệm ý câu nói: ngay trước đó Chi hỏi "Should we bring something back for you?" và Evers đặt "Get me a chicken sandwich" → "Sure thing" = sẽ mang đồ ăn về. | (A) đúng. | (B) công cụ — lạc. | (C) toạ độ đúng — ngược, đang có vấn đề. | (D) đo lại — không phải nghĩa câu."""),
 ("B", """Câu suy luận việc tiếp theo: Chi và Lim đi ăn trưa (không có Evers) rồi quay lại → "Ms. Chi and Ms. Lim will be out for a while". | (A) toạ độ mới — chưa chắc. | (B) đúng. | (C) chia sẻ công thức — không có. | (D) Lim bắt đầu đo — Evers mới là người đo."""),
],
"p7-05": [("A", """Câu đối tượng hướng tới: "Those of you wishing to donate surplus produce… growers" → nhà trồng trọt / nông dân. | (A) "Farmers" — đúng. | (B) đầu bếp — không. | (C) tài xế — họ là tình nguyện viên được nhắc, không phải người nhận thông báo. | (D) quản lý siêu thị — không."""),
 ("D", """Câu chi tiết: "excellent weather has yielded a substantial harvest" → thời tiết có lợi cho mùa màng. | (A) trễ vận chuyển — sai. | (B) mưa nhiều hơn — không nhắc. | (C) tin địa phương — không. | (D) đúng."""),
 ("B", """Câu chi tiết dịch vụ: thu gom produce dư thừa và "transport and quickly distribute your food donations" → thu phát thực phẩm. | (A) nhân sự — sai. | (B) đúng. | (C) sửa máy — sai. | (D) workshop làm vườn — Web có bài viết nhưng không phải "service"."""),
],
"p7-06": [("B", """Suy luận địa điểm: "performers", "audience members", ghi hình buổi biểu diễn → phòng hoà nhạc. | (A) máy bay — không có performer. | (B) đúng. | (C) nhà hàng — không. | (D) bưu điện — không."""),
 ("A", """Câu chi tiết túi lớn: "consider storing it in a locker for just $2" → tủ khoá có phí. | (A) "locked box for a fee" — paraphrase đúng. | (B) để ngoài toà nhà — sai. | (C) bị kiểm tra — sai. | (D) phải nhét dưới ghế — sai, nếu không nhét thì dùng locker."""),
 ("B", """Câu chèn: câu cần chèn nói về điện thoại/tin nhắn, nằm hợp nhất sau câu "put any and all electronic devices in silent mode. Ringtones and lit screens…" và trước "Moreover… recording" — tức vị trí [2]. | (A) [1] — trước phần nội quy. | (B) [2] — đúng. | (C) [3] — đoạn túi xách. | (D) [4] — đoạn gửi túi."""),
],
"p7-07": [("A", """Mục đích email: "Please review the attached order form and return it to me within seven days" → xin xác nhận đơn. | (A) đúng. | (B) đổi ngày giao — các ngày đã chốt. | (C) thông báo mở rộng — không. | (D) quảng bá món mới — có nhắc bánh mẫu nhưng không phải mục đích chính."""),
 ("C", """Suy luận về Ayala: "you chose us for a fourth year in a row" → khách hàng cũ nhiều năm. | (A) nhận giải — sai. | (B) làm pastry chef — sai, Adachi mới là chef. | (C) đúng. | (D) nhận giới thiệu — không."""),
 ("D", """Chi tiết bánh multilayer: "our head pastry chef will produce it according to your specifications. In fact, he created a sample of the complete recipe [for the] earlier filling" → công thức mới làm thử lần đầu → tổ hợp vị mới. | (A) best-selling — sai. | (B) đắt nhất — không có giá. | (C) bake hằng năm — sai, đơn năm nay. | (D) đúng."""),
 ("C", """Từ vựng: "We have judged it to be a delectable treat" — judged = kết luận/nhận thấy. | (A) criticized — nghĩa xấu. | (B) settled — dàn xếp. | (C) determined — đúng. | (D) described — mô tả, không phải phán xét vị."""),
],
"p7-08": [("C", """Chi tiết: "all of the reviews were excellent. So, I decided to spend the extra money" → chọn vì đánh giá tốt. | (A) rẻ hơn — ngược. | (B) lớn nhất — sai, "compact". | (C) "was rated very highly" — đúng. | (D) cùng thương hiệu — không nhắc."""),
 ("D", """Từ vựng: "the machine is so quiet, you do not even know it is running" — running = hoạt động. | (A) adjusting — sai. | (B) controlling — sai. | (C) moving — sai nghĩa máy chạy. | (D) "operating" — đúng."""),
 ("A", """Suy luận: "designed to use water efficiently, which is very important to me" → quan tâm tiết kiệm nước. | (A) đúng. | (B) chuyển nhà mới — chỉ remodel bếp. | (C) mua một năm trước — sai, "one month". | (D) cải tạo bếp chuyên nghiệp — sai, khách hàng cá nhân."""),
],
"p7-09": [("D", """Đối tượng: "We're growing fast and have many positions available… there's probably a place for you on our team" → người đang tìm việc. | (A) nhân viên hiện tại — benefits mô tả để thuyết phục, không phải thông báo nội bộ. | (B) khách hàng — sai. | (C) người mua tạp chí — Travel Vista chỉ là nguồn trích. | (D) đúng."""),
 ("B", """Câu NOT-except: được nêu là discount vé (không phải vé miễn phí), mentorship, tuition reimbursement, paid vacations. | (A) học phí — có nêu. | (B) "Free airline tickets" — KHÔNG có, chỉ là vé giá rẻ hơn → đáp án. | (C) mentoring — có. | (D) nghỉ phép lương — có."""),
 ("C", """Chi tiết: 'named "Best Airline to Work For" by Travel Vista Journal three years in a row' → được ca ngợi bởi ấn phẩm. | (A) nhiều điểm đến nhất — không so sánh. | (B) sáp nhập — không. | (C) đúng. | (D) đổi ghế — suy diễn từ "comfortable work-life balance"."""),
 ("A", """Câu chèn: "Our openings cover a broad range of skill sets" tiếp ngay "have many positions available" và dẫn tới "So regardless of your background…" → vị trí [1]. | (A) đúng. | (B) [2] — đoạn perks. | (C) [3] — ví dụ discount. | (D) [4] — đoạn mobility."""),
],
"p7-10": [("D", """Chi tiết: "ready for distribution to our many partner stores" → bản trình bày sẽ gửi nhiều nơi. | (A) tốn kém — không. | (B) best-selling — giới thiệu line tai nghe mới, không nói doanh số. | (C) dự án đầu tiên — không. | (D) đúng."""),
 ("B", """Hàm ý "let's not overlook that": Lorenz đồng tình với Woodson rằng số liệu user studies thể thao là phần còn thiếu → nhấn mạnh tầm quan trọng. | (A) thêm nhân sự — sai. | (B) đúng. | (C) chạy mượt — sai nghĩa. | (D) báo partner stores — sai."""),
 ("C", """Suy luận nghề Harven: người nắm summary báo cáo nghiên cứu R&D mà nhóm chờ → nhà nghiên cứu sản phẩm. | (A) quản lý cửa hàng — sai. | (B) vận động viên Amatơ — nhiễu từ "sport". | (C) đúng. | (D) quảng cáo — sai."""),
 ("C", """Chi tiết lịch: "Let's try for Thursday afternoon" để còn Friday sửa → họp duyệt vào Thursday. | (A) Monday gửi slides. | (B) Wednesday nhận báo cáo. | (C) đúng. | (D) Friday dự phòng sửa."""),
],
"p7-11": [("B", """Mục đích press release: "Kitchen Swifts and Chef Darius Cordero are joining together" → công bố hợp tác kinh doanh. | (A) mở nhà hàng — Enriqua's "recently opened" chỉ là chi tiết về chef. | (B) đúng. | (C) du lịch — nhiễu từ "travelling the world". | (D) chúc mừng award — "award-winning" là tính từ dẫn."""),
 ("C", """Từ vựng: "his cooking reflects his Filipino heritage" — reflects = thể hiện. | (A) results in — ngược quan hệ. | (B) changes — sai. | (C) "shows" — đúng. | (D) thinks about — sai."""),
 ("C", """Chi tiết Kitchen Swifts: "menus, recipes, and ingredients for two people, four people, or six people… vegetarian selections" → nhiều lựa chọn bữa. | (A) tăng giá — ngược "no price increase". | (B) đổi lịch giao — không. | (C) đúng. | (D) VP mới — Chambers đương nhiệm."""),
 ("A", """Suy luận về Guan: review "eat at Enriqua's" = nhà hàng của Cordero → đã ăn tại nhà hàng của chef. | (A) đúng. | (B) nghỉ dưỡng — đi conference, không phải vacation. | (C) đồng nghiệp Chambers — "A colleague arranged" là người khác xếp. | (D) thường xuyên order KitSwifts — không có."""),
 ("B", """Chi tiết review: "usually fully booked for dinner; you may need to call months in advance for a table" → có nhận đặt bàn bữa tối. | (A) lunch menu hạn chế — ngược, lunch vẫn phục vụ. | (B) đúng. | (C) bánh mì tiệm khác — "baked on-site" ngược. | (D) có chi nhánh Hong Kong — Guan bay về HK."""),
],
"p7-12": [("A", """Mục đích email: Boyle chốt phương án tự giao hàng, ngày giờ "no later than 5 p.m." on 5 June → xác nhận kế hoạch. | (A) "To finalize a plan" — đúng. | (B) nhận lời mời — không có lời mời. | (C) quảng bá dịch vụ — không. | (D) xin phản hồi chính sách — không."""),
 ("D", """Chi tiết tuyến đường: "my sister and her children live nearby in Kirkcolm. Before seeing them, I will drive… to your house" → tới Kirkcolm để thăm gia đình. | (A) giao hàng — giao tới nhà Savard ở Stranraer, ngược chiều. | (B) họp — không. | (C) trả xe thuê — không. | (D) đúng."""),
 ("B", """Suy luận chính sách giao hàng: "I've seen too much damage done by inattentive baggage handlers" → thất vọng với hãng bay/tàu hoả. | (A) chị đồng sáng lập — không. | (B) đúng. | (C) Savard từng mua — "As you know" chưa chắc từng mua. | (D) sở thích hành lý — sai, "my merchandise" — sai, "my merchandise"."""),
 ("C", """Suy luận về Savard: đề nghị trước là "pick up your online order… or pay extra for air or train transport" — cô đặt hàng online → khách đã mua của Boyle; "kind offer" của cô cho thấy quan hệ mua bán trước đó. | (A) đi công tác — suy diễn. | (B) trả thêm tiền giao tận nơi — ngược, "Neither arrangement is necessary". | (C) đúng nhất — từng mua hàng của Boyle. | (D) gặp ở chỗ thuê xe — Boyle tới tận nhà."""),
 ("C", """Chi tiết vé phà: "Departing Belfast… Docking at Cairnryan" + Ferry Service → đi bằng tàu thuỷ. | (A) ô tô — thuê xe để đi tiếp ở bên kia. | (B) tàu hoả — sai. | (C) đúng. | (D) máy bay — sai."""),
],
"p7-13": [("C", """Chi tiết quảng cáo: "taught by recognized professionals in their respective fields" → lớp do chuyên gia ngành đứng lớp. | (A) founder là graphic designer — không nhắc. | (B) tự xuất bản newsletter — "Profiled in the latest Business Directions Nigeria newsletter" là tạp chí khác. | (C) đúng. | (D) có cơ sở khắp West Africa — lớp 100% online."""),
 ("D", """Chi tiết: "Upon successful completion… you will receive an official Certificate of Training" → chứng chỉ. | (A) "A…" (dòng option bị OCR cắt — mất chữ, cần đối chiếu sách; không ảnh hưởng đáp án). | (B) giảm giá khoá sau — không. | (C) danh sách việc làm — không. | (D) đúng."""),
 ("B", """Suy luận về Egbe: "I remembered chatting with some of you on the forum for January's poster design class" → từng học khoá TTA trước. | (A) thiết kế forum — sai. | (B) đúng. | (C) phát triển phần mềm họp — sai. | (D) đã bán xe bánh mì — "I own a food truck" vẫn sở hữu."""),
 ("A", """Chi tiết: Egbe "met with Mr. Akpan for an individual videoconference" — Akpan dạy Introduction to Social Media Marketing → cậu học lớp đó. | (A) đúng. | (B) Akande. | (C) Kabiru. | (D) Umaru."""),
 ("B", """Suy luận: Akpan khuyên "add a section with vivid images of all my baked goods" → mục xem ảnh = Section 2 "Browse photos".""" ),
],
"p7-14": [("D", """Chi tiết article: "has been serving… for six months now" → mở cách đây sáu tháng. | (A) đang tuyển server — "servers are always happy" ≠ tuyển. | (B) phố yên tĩnh — "bustling shops" ngược. | (C) chi nhánh Jamaica — chỉ nói hương vị Jamaica. | (D) đúng."""),
 ("C", """Chi tiết: "most famous for its jerk chicken" → món nổi tiếng nhất. | (A)(B)(D) đều là món trong menu nhưng không phải "most famous". | (C) đúng."""),
 ("A", """Suy luận từ review: cô tới "on any Friday night between 7 and 11" để nghe nhạc sống và "arrived there at 7 P.M. yesterday, keen to enjoy live music" → tối hôm đó là Friday. | (A) đúng. | (B) ăn một mình — đi cùng chồng. | (C) xin thêm cơm — không. | (D) gọi tráng miệng — gọi thêm appetiser."""),
 ("B", """Mục đích email của owner: "Thank you… our failure to live up to your expectations… Please accept the attached £20 gift certificate" → xin lỗi và bồi đắp. | (A) trả lời câu hỏi — không có câu hỏi. | (B) đúng. | (C) xin feedback — review đã có rồi. | (D) xác nhận đặt bàn — không."""),
 ("C", """Chi tiết: "The head chef came out to apologise" và email xác nhận "Head Chef Adio Brown" → cô gặp Mr. Brown. | (A) Roats là phóng viên. | (B) Deslandes — chỉ được nhắc tên. | (C) đúng. | (D) Smith — chủ gửi email, không gặp tại quán."""),
],
"p7-15": [("A", """Suy luận từ hoá đơn (bảng phẳng, chờ ảnh xác tín): mặt hàng "(0.6x0.6m)" + đơn vị tính theo tấm/vị trí công trình gợi ý Green Canyon làm cảnh quan. | (A) "It does landscaping projects" — hợp nhất với tên Green Canyon và kích thước mặt hàng; lưu ý cần ảnh hoá đơn để chốt. | (B) thiết kế đường — không. | (C) sửa nhà cũ — không. | (D) trang trại — nhiễu từ "Green"."""),
 ("C", """Chi tiết hoá đơn: tổng dòng tiền "4,535.00" (> $4,000) khớp ưu đãi "10% discount for orders of more than $4,000" trong notice → giảm vì chi nhiều. | (A) tổ chức từ thiện — không có dấu hiệu. | (B) Frequent Buyer Club — không chứng minh. | (C) đúng. | (D) gần supply center — miễn phí vận chuyển ≠ giảm giá."""),
 ("C", """Chi tiết notice: "we are switching to electronic invoicing" → hệ thống hoá đơn đổi. | (A) email address — sai. | (B) list of incentives — "remain in place" không đổi. | (C) đúng. | (D) lịch giao — không."""),
 ("D", """Suy luận: "one of our very first customers" + công ty "founded over twenty years ago" → khách ~20 năm. | (A) xin gặp Singh — không. | (B) xin việc — sai. | (C) vừa mua máy xây — August invoice là hoá đơn định kỳ. | (D) đúng."""),
 ("B", """Chi tiết email: "could you please investigate the problem… and send the invoice for August" → yêu cầu xử lý vấn đề. | (A) trả hoá đơn — sai người trả. | (B) đúng. | (C) xác nhận đơn — không. | (D) cập nhật số tài khoản — không."""),
],
}


def patch(fp, entries):
    t = fp.read_text()
    if "Explanation:" in t:
        return "đã có"
    seg = t.split("[QUESTION]")
    changed = 0
    for k, (ans, expl) in enumerate(entries):
        if k + 1 >= len(seg):
            continue
        body = seg[k + 1]
        if "Answer:" not in body:
            if "Source:" in body:
                body = body.replace("Source:", f"Answer: {ans}\nExplanation: {D}{expl}\nSource:", 1)
            else:
                body = body.rstrip("\n") + f"\nAnswer: {ans}\nExplanation: {D}{expl}\n"
            changed += 1
        else:
            if "Source:" in body:
                body = body.replace("Source:", f"Explanation: {expl}\nSource:", 1)
            else:
                body = body.rstrip("\n") + f"\nExplanation: {expl}\n"
            changed += 1
        seg[k + 1] = body
    fp.write_text("[QUESTION]".join(seg))
    return f"+{changed}"


if __name__ == "__main__":
    root = Path(sys.argv[1])
    miss = []
    for fp in sorted(root.glob("p7-*.txt")):
        k = fp.name[:-4]
        if k in E7:
            print(k, patch(fp, E7[k]))
        else:
            miss.append(k)
    print("BỎ SÓT:", miss or "không")
