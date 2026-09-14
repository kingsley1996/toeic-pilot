# ruff: noqa: E501, W291
"""Thêm Answer+suy-ra + Explanation cho P2/P5/P6 của tp-2024-NN (idempotent).

    uv run python scripts/add_explanations_2024.py content/generated/tp-2024-01/paste

P2 có Answer in sẵn trong sách → explanation bám đáp án đó. P5/P6 sách không
in đáp án → đáp án DẪN XUẤT từ ngữ pháp/ngữ cảnh, đánh dấu "(dẫn xuất)" trong
Explanation để đời sau biết không phải của ETS. Không đụng tệp đã có Explanation.
"""
import sys
from pathlib import Path

E2 = {
"p2-01": ("B", """Câu hỏi "How old…?" hỏi tuổi của toà nhà. | (A) "To ship some materials." — trả lời cho câu hỏi mục đích Why, lệch kiểu hỏi. | (B) "About ten years old." — nêu đúng số tuổi được hỏi. | (C) "Company offices, I think." — trả lời "What is in the building?", dùng lại chủ đề building làm nhiễu."""),
"p2-02": ("C", """Câu hỏi "Can you come…?" là lời mời dự buổi biểu diễn jazz tối nay. | (A) "I'm sorry I was late for the meeting." — xin lỗi đi muộn, không liên quan lời mời. | (B) "Mostly just local musicians." — trả lời "Who plays in the band?", nhiễu từ nhóm nhạc. | (C) "Sure, I'll be there!" — nhận lời mời đúng nghĩa."""),
"p2-03": ("C", """Câu hỏi "Which apartment…?" hỏi căn hộ nào gửi phiếu yêu cầu sửa chữa. | (A) "It's what you did a living." — câu về nghề nghiệp, vô nghĩa với Which. | (B) "Submit your assignment here." — mệnh lệnh lặp lại động từ submit để nhiễu. | (C) "It came from the tenants in B23." — chỉ đúng căn hộ được hỏi."""),
"p2-04": ("A", """Câu hỏi "Will you contact the vendor…?" nhờ liên hệ nhà cung cấp đổi ngày giao hàng. | (A) "Of course, I'll take care of it." — nhận làm việc được nhờ. | (B) "An e-mail receipt." — trả lời "What did you get?", nhiễu phương tiện. | (C) "Could I get change for a dollar?" — nhiễu từ "changing" bị lái thành "change" (tiền thừa)."""),
"p2-05": ("C", """Câu hỏi "Why…?" hỏi lý do nhân viên bảo trì có mặt ở đây. | (A) "No, he didn't." — trả lời Yes/No với Did, không khớp Why. | (B) "From three o'clock until four." — trả lời When/How long. | (C) "Because a light needed to be fixed." — mệnh đề Because chỉ đúng lý do."""),
"p2-06": ("C", """Câu hỏi Yes/No: ban lãnh đạo đã chốt quyết định tuyển dụng chưa. | (A) "Put it on the highest shelf." — mệnh lệnh vị trí, vô nghĩa. | (B) "The personnel department." — trả lời "Which department", nhiễu chủ đề nhân sự. | (C) "Yes, they chose Jacob Borgman." — xác nhận rồi và nêu người được chọn."""),
"p2-07": ("C", """Câu hỏi lựa chọn: ăn ở căng-tin hay ra ngoài. | (A) "He went there yesterday." — nói người khác, lạc chủ đề. | (B) "Well, maybe a sandwich." — chọn món ăn chứ không chọn nơi ăn. | (C) "Let's eat here." — quyết định đúng vế được hỏi."""),
"p2-08": ("B", """Câu hỏi phủ định: đã gửi hợp đồng lao động cho ông Patel hôm qua chưa. | (A) "Yes, I would agree." — bày tỏ đồng tình, không xác nhận việc đã gửi. | (B) "No, I'll send it now." — nhận chưa gửi và sẽ gửi ngay, đúng thực tế được hỏi. | (C) "Check the employee manual." — mệnh lệnh nhiễu từ employment/employee."""),
"p2-09": ("A", """Câu xác nhận hỏi lại: picnic của phòng là thứ Bảy này phải không. | (A) "There's a lot of rain in the forecast." — lo thời tiết cho sự kiện ngoài trời cuối tuần, hồi âm tự nhiên nhất. | (B) "Sure, I like salad" — đáp "Do you like…?", nhiễu món ăn. | (C) "At the end of this corridor." — trả lời Where."""),
"p2-10": ("A", """Câu hỏi lựa chọn đồ uống: coffee hay tea. | (A) "Just water, please." — chọn phương án khác một cách lịch sự. | (B) "For a few dollars more." — nhiễu giá tiền. | (C) "A fifteen-minute break." — trả lời How long, lạc chủ đề."""),
"p2-11": ("A", """Câu trần thuật thông báo: tháng này phòng đạt chỉ tiêu doanh số. | (A) "That's excellent news!" — phản ứng khen trước tin tốt. | (B) "A few times a day." — trả lời How often. | (C) "To the end of April." — trả lời Until when, nhiễu mốc thời gian."""),
"p2-12": ("C", """Câu hỏi "How often…?" hỏi tần suất đi công tác. | (A) "It turned out well." — đánh giá kết quả, vô nghĩa. | (B) "Yes, I did find one." — trả lời Yes/No, lệch How often. | (C) "About once a month." — nêu đúng tần suất."""),
"p2-13": ("B", """Câu gợi ý: hôm nay đi bộ đường dài trên lối Wildflower Trail. | (A) "This seat is available." — nhường chỗ, lạc chủ đề. | (B) "I didn't bring boots." — nêu trở ngại cho việc hiking, đáp tự nhiên. | (C) "At the visitors' center." — trả lời Where, nhiễu bối cảnh du lịch."""),
"p2-14": ("C", """Câu hỏi đuôi: bạn đã đặt khách sạn ở London rồi phải không. | (A) "Very enjoyable, thanks." — đáp khi được hỏi trải nghiệm. | (B) "He usually takes the train." — nói người khác và phương tiện. | (C) "Yes, I made a reservation last week." — xác nhận; reservation đồng nghĩa booked."""),
"p2-15": ("A", """Câu hỏi: còn vé cho buổi hoà nhạc tối nay không. | (A) "It's sold out." — trả lời trực tiếp: đã bán hết. | (B) "He's a concert violinist." — nhiễu từ concert nhưng nói về người. | (C) "They already left." — nhiễu từ left (rời đi ≠ còn lại)."""),
"p2-16": ("B", """Câu hỏi phủ định: bạn chưa dùng phần mềm này bao giờ à. | (A) "Can I take your order?" — câu gọi món, vô nghĩa. | (B) "I haven't had the chance." — nhận chưa có dịp dùng, khớp thì hoàn thành được hỏi. | (C) "About 40 dollars." — trả lời How much."""),
"p2-17": ("C", """Câu hỏi When: máy xay sinh tố mới ra mắt khi nào. | (A) "Only with fruits and vegetables." — trả lời With what, nhiễu công dụng. | (B) "In the kitchen cabinet." — trả lời Where, nhiễu đồ bếp. | (C) "The prototype is still being tested." — giải thích chưa có ngày cụ thể vì còn thử nghiệm."""),
"p2-18": ("A", """Câu hỏi Who: ai đón khách của ta ở sân bay. | (A) "They decided to drive." — họ (nhóm được phân công) quyết định lái xe đi đón, giữ đúng chủ ngữ chỉ người. | (B) "At terminal 2." — trả lời Where. | (C) "It's a marketing position." — trả lời What kind of job."""),
"p2-19": ("C", """Câu hỏi Where: mấy bó hoa hồng đỏ nhập sáng nay để ở đâu. | (A) "About three liters of water." — trả lời lượng nước. | (B) "No, I didn't check out the sale." — Yes/No về khuyến mãi, không khớp. | (C) "I needed some for a large bouquet." — cho biết số hoa đã được lấy cắm bó rồi — ám chỉ vị trí, kiểu đáp từ chối-tại-vì đúng ngữ cảnh TOEIC."""),
"p2-20": ("A", """Câu trần thuật: phim này được đề cử several awards. | (A) "Why don't we go see it?" — gợi ý đi xem vì phim đang được chú ý, đáp tự nhiên. | (B) "After the announcement." — trả lời When. | (C) "He made a great speech." — thêm nhân vật không có trong chuyện."""),
"p2-21": ("B", """Câu hỏi Who: ai quan tâm việc lập chương trình đi chung xe (car pool). | (A) "Thanks, but I can't swim." — từ chối chuyện bơi, vô nghĩa. | (B) "Clara's already organizing one." — nêu người đang tổ chức, đúng Who. | (C) "It's a very interesting article." — nhiễu "interested" nhưng nói về bài báo."""),
"p2-22": ("A", """Câu hỏi Where: tháng này tôi dạy workshop ở đâu. | (A) "We just sent an e-mail to all instructors." — chỉ nguồn tra cứu cho chính người hỏi là giảng viên, đáp tự nhiên. | (B) "Five to seven months." — trả lời How long. | (C) "Yes, it's a beautiful building." — Yes lạc với Where."""),
"p2-23": ("C", """Câu hỏi Why: tại sao chuyển áo len ra phía sau cửa hàng. | (A) "In the new shopping mall." — trả lời Where. | (B) "Yes, they come in other colors." — Yes/No lệch Why. | (C) "Our spring merchandise is arriving soon." — hàng xuân sắp về nên phải dành chỗ, đúng lý do."""),
"p2-24": ("C", """Câu hỏi mời nhận xử lý vài hợp đồng. | (A) "Thank you for meeting me." — cảm ơn buổi hẹn, không trả lời lời mời. | (B) "A contact lens prescription." — nhiễu "contract" gần âm "contact". | (C) "I have very limited time." — từ chối khéo vì ít thời gian."""),
"p2-25": ("B", """Câu hỏi What type: bạn đang tìm loại công việc nào. | (A) "No, at ten A.M." — trả lời giờ giấc. | (B) "I really like working with computers." — nêu sở thích nghề, đúng trọng tâm. | (C) "Just a résumé is needed." — nói thủ tục hồ sơ, không tả loại việc."""),
}

E5 = {
"p5-01": ("B", """Chỗ trống đứng trước cụm danh từ "career experiences" cần tính từ sở hữu. | (A) "he" — đại từ chủ ngữ. | (B) "his" — tính từ sở hữu, "his career experiences" đúng. | (C) "him" — đại từ tân ngữ. | (D) "himself" — phản thân, không bổ nghĩa danh từ."""),
"p5-02": ("D", """Chỗ trống trước "domestic flight" cần phân từ bổ nghĩa kiểu chuyến bay nối chuyến. | (A) "connectivity" — danh từ. | (B) "connects" — động từ chia ngôi. | (C) "connect" — động từ nguyên thể. | (D) "connecting" — "a connecting flight" là cụm cố định."""),
"p5-03": ("C", """Chỗ trống song song với tính từ "Fresh" trước "apple-cider donuts" cần tính mô tả chất lượng. | (A) "eaten" — nghĩa lạ. | (B) "open" — không tả đồ ăn. | (C) "tasty" — "Fresh and tasty donuts" tự nhiên. | (D) "free" — mâu thuẫn giá £6 mỗi dozen."""),
"p5-04": ("B", """Zahn Flooring là công ty sàn nhà, nên "widest selection of…" phải là mặt hàng ngành sàn. | (A) "paints" — sơn. | (B) "tiles" — gạch lát, đúng ngành flooring. | (C) "furniture" — nội thất. | (D) "curtains" — rèm."""),
"p5-05": ("D", """Chỗ trống trước danh từ "software" cần phân từ bị động làm tính từ. | (A) "update" — động từ/danh từ. | (B) "updating" — chủ động, phần mềm không tự cập nhật. | (C) "updates" — động từ. | (D) "updated" — "updated software" phần mềm đã cập nhật, đúng."""),
"p5-06": ("D", """Cần giới từ quan hệ thời gian: kiểm dress code ___ đến trụ sở. | (A) "so" — kết quả, sai. | (B) "how" — không liên kết được V-ing. | (C) "like" — so sánh, sai nghĩa. | (D) "before" — "before visiting" đúng."""),
"p5-07": ("A", """Chỗ trống bổ nghĩa động từ "support" cần trạng từ. | (A) "enthusiastically" — đúng vị trí. | (B) "enthusiasm" — danh từ. | (C) "enthusiastic" — tính từ. | (D) "enthused" — không chuẩn."""),
"p5-08": ("D", """Song song với danh từ số nhiều "Wheel alignments": "brake system ___" cần danh từ. | (A) "inspects" — động từ. | (B) "inspector" — chỉ người. | (C) "inspected" — quá khứ. | (D) "inspections" — "brake system inspections" đúng."""),
"p5-09": ("A", """"Registration is open ___ September 30" cần giới từ mốc kết thúc. | (A) "until" — mở đến hết 30/9, đúng. | (B) "into" — sai. | (C) "yet" — trạng từ câu phủ định. | (D) "while" — cần mệnh đề."""),
"p5-10": ("B", """"Growth has been ___ this quarter" cần tính mô tả mức tăng trưởng. | (A) "separate" — vô nghĩa. | (B) "limited" — tăng trưởng hạn chế, tự nhiên. | (C) "willing" — chỉ người. | (D) "assorted" — không đi với growth."""),
"p5-11": ("A", """Cần danh từ sau động từ make. | (A) "deliveries" — "make deliveries" thực hiện việc giao hàng, đúng cụm. | (B) "delivered" — quá khứ. | (C) "deliver" — nguyên thể. | (D) "deliverable" — tính từ/tài liệu."""),
"p5-12": ("B", """"authority to ___ parking on city streets" — động từ hợp thẩm quyền hội đồng thành phố. | (A) "drive" — sai. | (B) "prohibit" — cấm đậu xe, đúng. | (C) "bother" — vô nghĩa. | (D) "travel" — sai."""),
"p5-13": ("A", """Cần động từ đi với giới từ for. | (A) "looking" — "looking for ways" tìm cách, đúng. | (B) "seeing" — không đi with for ways. | (C) "driving" — sai. | (D) "leaning" — sai giới từ."""),
"p5-14": ("C", """Chỗ trống cuối câu bổ nghĩa động từ "fits" cần trạng từ. | (A) "perfect" — tính từ. | (B) "perfects" — động từ. | (C) "perfectly" — trạng từ đúng. | (D) "perfection" — danh từ."""),
"p5-15": ("D", """"has proved to be very ___ with…" cần tính từ sau to be. | (A) "helpfulness" — danh từ. | (B) "help" — danh/động từ. | (C) "helpfully" — trạng từ. | (D) "helpful" — "helpful with" đúng."""),
"p5-16": ("C", """Cần giới từ chỉ khoảng thời gian "the month of August". | (A) "onto" — sai. | (B) "above" — sai. | (C) "during" — trong suốt tháng 8, đúng. | (D) "between" — cần hai mốc."""),
"p5-17": ("D", """"not received ___ enough to be used" cần trạng từ thời gian đi với enough. | (A) "far" — sai. | (B) "very" — không đủ cấu trúc. | (C) "almost" — sai. | (D) "soon" — "not soon enough" không kịp, đúng."""),
"p5-18": ("B", """"role of event ___" cần danh từ chỉ người. | (A) "organized" — tính từ. | (B) "organizer" — "event organizer" người tổ chức sự kiện, khớp lý lịch former publicist. | (C) "organizes" — động từ. | (D) "organizational" — tính từ."""),
"p5-19": ("A", """Chỗ trống bổ nghĩa "closed" cần trạng từ kiểu đóng đường do công trình. | (A) "temporarily" — đóng tạm thời, đúng. | (B) "competitively" — vô nghĩa. | (C) "recently" — mâu thuẫn thì tương lai. | (D) "collectively" — sai."""),
"p5-20": ("A", """Cặp giới từ liệt kê "___ missed connections to lost luggage". | (A) "from" — "from X to Y" đúng cặp. | (B) "under" — sai. | (C) "on" — sai. | (D) "against" — sai."""),
"p5-21": ("D", """Chỗ trống bổ nghĩa "deleted" cần trạng từ. | (A) "accident" — danh từ. | (B) "accidental" — tính từ. | (C) "accidents" — danh từ nhiều. | (D) "accidentally" — "vô tình bị xoá", đúng."""),
"p5-22": ("A", """"rise 5 percent over the ___ year" — dự báo cần mốc tương lai. | (A) "next" — "over the next year" trong năm tới, đúng. | (B) "with" — sai. | (C) "which" — sai. | (D) "now" — sai với dự báo."""),
"p5-23": ("B", """Mệnh đề đề quan hệ với "Anyone who still ___": chủ ngữ số ít. | (A) "needing" — thiếu trợ động từ. | (B) "needs" — hiện tại số ít, đúng. | (C) "has needed" — hoàn thành sai nghĩa "vẫn còn phải học". | (D) "were needing" — sai số ít."""),
"p5-24": ("A", """Chỗ trống giữa have…begun cần trạng từ đi với thì hoàn thành. | (A) "already" — đã bắt đầu, đúng. | (B) "exactly" — sai. | (C) "hardly" — phủ định, ngược nghĩa câu khen transformative. | (D) "closely" — sai."""),
"p5-25": ("D", """"high ___ that employees are expected to meet" cần danh từ đi với meet. | (A) "experts" — meet experts vô nghĩa. | (B) "accounts" — sai. | (C) "recommendations" — không đi meet chuẩn. | (D) "standards" — "high standards to meet" chuẩn mực phải đạt, đúng."""),
"p5-26": ("D", """Cần lượng từ với "of the board members" số nhiều khẳng định. | (A) "any" — thiên phủ định/nghi vấn. | (B) "everybody" — không đi of + danh từ xác định. | (C) "those" — sai cấu trúc. | (D) "some" — một số thành viên, đúng."""),
"p5-27": ("C", """"The project ___ the collaboration of several teams" cần động từ tân ngữ hợp nghĩa. | (A) "passed" — sai. | (B) "decided" — sai. | (C) "required" — dự án đòi hỏi hợp tác, đúng. | (D) "performed" — sai nghĩa."""),
"p5-28": ("C", """Sau until cần hiện tại (không will), và by Ms. Jeon bắt buộc bị động. | (A) "is approving" — chủ động. | (B) "approves" — chủ động. | (C) "has been approved" — bị động hoàn thành, đúng. | (D) "will be approved" — cấm will sau until."""),
"p5-29": ("C", """Vế đầu là NGUYÊN NHÂN của việc tìm hãng vận chuyển mới. | (A) "In spite of" — ngược nghĩa (mặc dù). | (B) "Just as" — cần mệnh đề thời gian. | (C) "In light of" — vì/trước việc, đúng. | (D) "According to" — trích nguồn, sai."""),
"p5-30": ("B", """Tính từ mô tả thông tin của tờ rơi giúp người vay hiểu điều khoản. | (A) "arbitrary" — tuỳ hứng, nghĩa xấu. | (B) "supplemental" — bổ trợ, đúng vai tờ rơi. | (C) "superfluous" — dư thừa, nghĩa xấu. | (D) "potential" — sai."""),
}

E6 = {
"p6-01": [
 ("D", """Chỗ (1) đứng riêng thành một câu giữa phần giới thiệu và "We will teach you…", cần câu nêu hoạt động cụ thể của trung tâm. | (A) "exhibits" — trung tâm làm vườn, không có khu trưng bày. | (B) "rainfall patterns" — lạc sang khí tượng. | (C) "patio furniture" — đóng đồ gỗ, sai ngành. | (D) thông báo workshop miễn phí cho công chúng — khớp mạch mời đến học."""),
 ("D", """Chỗ (2) nối "a shallow sunken garden ___ a special soil mix": cần mệnh đề quan hệ cho garden. | (A) "to use" — sai cấu trúc sau danh từ. | (B) "used to" — nghĩa "đã từng". | (C) "by using" — không hợp vị trí. | (D) "that uses" — khu vườn sử dụng hỗn hợp đất, đúng."""),
 ("A", """Chỗ (3) mở đầu câu tổng kết lợi ích "rain gardens are always beneficial". | (A) "Best of all" — chốt ưu điểm lớn nhất, đúng vị trí. | (B) "For example" — câu sau không phải ví dụ. | (C) "In any event" — "dù sao đi nữa" lạc. | (D) "As a matter of fact" — ngữ khí phản biện, không hợp."""),
 ("B", """Chỗ (4) là chủ ngữ cho "improve drainage", thay cho rain gardens (số nhiều). | (A) "we" — sai ngôi. | (B) "they" — chỉ rain gardens, đúng. | (C) "both" — không có hai đối tượng được nêu. | (D) "yours" — sở hữu, sai."""),
],
"p6-02": [
 ("C", """Chỗ (1) trước danh từ "support" cần tính từ. | (A) "amazed" — cảm nhận của người. | (B) "amazement" — danh từ. | (C) "amazing" — "your amazing support" sự hỗ trợ tuyệt vời, đúng. | (D) "amazingly" — trạng từ."""),
 ("A", """Chỗ (2) "received a lot of ___ on social media" trong mạch khen thiết kế. | (A) "attention" — sự chú ý, hợp. | (B) "proposals" — sai. | (C) "innovation" — không "received". | (D) "criticism" — trái chiều khen."""),
 ("B", """Chỗ (3) là một câu trong chuỗi cảm ơn; câu ngay sau nhắc "multiple delays" → cần câu về sự linh hoạt khi lên kế hoạch. | (A) "Several other events…" — lạc hướng xin lỗi. | (B) "Thank you also for your flexibility in planning the event." — khớp delays. | (C) "Please stop by our office…" — mời, chưa đúng chỗ. | (D) "Tokyo is a top tourism…" — lạc sang du lịch."""),
 ("B", """Chỗ (4) "The auction ___ our Young Designers Award program is coming up soon" — động từ chính đã là is coming, nên chỗ trống phải là infinitive chỉ mục đích bổ nghĩa auction. | (A) "will benefit" — thừa thì. | (B) "to benefit" — cuộc đấu giá gây quỹ cho chương trình, đúng. | (C) "has benefited" — thừa thì. | (D) "benefits" — thừa thì."""),
],
"p6-03": [
 ("A", """Chỗ (1) là chủ ngữ cho "must be renewed", thay cho "your Mena Chin Library card". | (A) "It" — chỉ cái thẻ, đúng. | (B) "You" — người không bị gia hạn. | (C) "Our" — cần danh từ đi sau. | (D) "Each" — sai."""),
 ("C", """Chỗ (2) nằm giữa hai câu về gia hạn; câu sau "This can be done at the information desk" → câu trước phải nêu việc cần làm và thời hạn. | (A) "sign up for a card" — người nhận đã có thẻ. | (B) "For questions…" — trùng ý đoạn cuối thư. | (C) "Renewal must be completed at least one week before your card expires." — khớp This. | (D) "opt out" — sai chủ đề."""),
 ("B", """Chỗ (3) mở câu điều kiện đảo: "___ you decide to close your account, no action is necessary". | (A) "Also" — không tạo điều kiện. | (B) "Should" — "Should you decide" = If you decide, cấu trúc trang trọng chuẩn thư thông báo. | (C) "Because" — logic ngược. | (D) "Although" — nhượng bộ sai."""),
 ("C", """Chỗ (4) trước danh từ "date" cần tính từ. | (A) "specifically" — trạng từ. | (B) "specifics" — danh từ. | (C) "specified" — ngày hạn đã được nêu rõ, đúng. | (D) "specificity" — danh từ."""),
],
"p6-04": [
 ("A", """Chỗ (1) ngay sau câu tự giới thiệu "I am Omar Ridha, the manager…" — cần câu mở quan hệ kinh doanh. | (A) "I would like to introduce you to our business." — đúng vị trí thư chào hàng. | (B) "Great photographs can make your property stand out." — ý này đã có ở câu sau. | (C) "looking forward to your visit" — chưa có hẹn nào. | (D) "first studio of its kind" — thông tin hình thành, lạc chỗ mở."""),
 ("B", """"spares no effort in ___ superior digital images" — cần V-ing hợp vai studio ảnh. | (A) "researching" — sai. | (B) "creating" — tạo ảnh số chất lượng cao, đúng. | (C) "purchasing" — studio không đi mua ảnh. | (D) "displaying" — lạc."""),
 ("D", """Chỗ (3) nối hai câu cùng chiều khen trang thiết bị → cần trạng từ củng cố. | (A) "If not" — điều kiện ngược. | (B) "By comparison" — không có đối tượng so sánh. | (C) "Otherwise" — hệ quả ngược. | (D) "Indeed" — quả thực, đúng."""),
 ("A", """"every image ___ expert editing" là câu mô tả quy trình chung, cần hiện tại đơn. | (A) "receives" — đúng thì, đúng nghĩa. | (B) "is receiving" — tiếp diễn không hợp quy trình từng-loạt-ảnh. | (C) "had received" — quá khứ hoàn thành sai. | (D) "had to receive" — nghĩa bắt buộc quá khứ, sai."""),
],
}

DERIVED = """(đáp án dẫn xuất từ ngữ pháp/ngữ cảnh — sách in GIẢI không kèm đáp án phần này) """


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
                body = body.replace("Source:", f"Answer: {ans}\nExplanation: {DERIVED}{expl}\nSource:", 1)
            else:
                body = body.rstrip("\n") + f"\nAnswer: {ans}\nExplanation: {DERIVED}{expl}\n"
            changed += 1
        else:
            if "Source:" in body:
                body = body.replace("Source:", f"Explanation: {expl}\nSource:", 1)
            else:
                body = body.rstrip("\n") + f"\nExplanation: {expl}\n"
            changed += 1
        seg[k + 1] = body
    fp.write_text("[QUESTION]".join(seg))
    return f"đã thêm {changed}"


if __name__ == "__main__":
    root = Path(sys.argv[1])
    miss = []
    for fp in sorted(root.glob("p2-*.txt")):
        k = fp.name[:-4]
        if k in E2:
            print(f"{k}: {patch(fp, [E2[k]])}")
    for fp in sorted(root.glob("p5-*.txt")):
        k = fp.name[:-4]
        if k in E5:
            print(f"{k}: {patch(fp, [E5[k]])}")
        else:
            miss.append(k)
    for fp in sorted(root.glob("p6-*.txt")):
        k = fp.name[:-4]
        if k in E6:
            print(f"{k}: {patch(fp, E6[k])}")
    # p2 thiếu file (vị trí chờ vá tay) im lặng là bình thường
    print("BỎ SÓT:", miss or "không")
