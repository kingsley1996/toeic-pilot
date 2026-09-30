# Siêu thị — đặc tả cảnh 3D (`supermarket-aisles-01`, topic `supermarket`, 24 từ)

## 1. Danh sách từ (headword | pos — toàn bộ đã có trong paste nhập mới)

aisle, shelf, cart, basket, checkout, cashier, receipt, barcode, produce,
dairy, freezer, bakery, deli, coupon, discount, sample, scale, price-tag,
promotion, shopping-list, entrance, exit, bag, refund.

TOEIC-fit: Part 1 (ảnh quầy/kệ), Part 2 (Where is the receipt?/coupons),
Part 4 (store announcements: discount/promotion), Part 7 (receipt/coupon/
refund notice). `refund` neo vào quầy dịch vụ khách hàng — đúng đời và đúng đề.

## 2. Bố cục nam→bắc (sảnh trong nhà ~30 × 22 m, tường cao 4 m)

- Nam (z 10): tường kính — `entrance` (x −6) + `exit` (x +6) hai cửa trượt;
  giữa là bảng `shopping-list` + chồng `basket` cạnh cửa vào.
- Giữa: 3 dãy `shelf` song song trục Z (x −6/0/6, dài 8 m), hai `aisle`
  ở giữa; `cart` patrol dọc aisle giữa; xe nền decor đứng yên ở aisle bên.
- Đông: `produce` (sạp rau, có `scale`) + `sample` (khay mẫu trên chân đứng).
- Tây: `dairy` (kệ sữa mở) + `freezer` (tủ đông nắp kính) sát tường.
- Bắc (z −8): 3 quầy `checkout` song song trục X + `cashier` đứng quầy giữa;
  `bag` (chồng túi giấy) + `receipt`/`barcode` trên mặt quầy; `promotion`
  (tháp hàng khuyến mãi) giữa sảnh trước quầy; `coupon` + `discount` là biển
  treo trên quầy (mặt +Z về camera); `refund` (quầy dịch vụ KH) góc tây-bắc;
  `bakery` đông-bắc, `deli` tây-bắc (hai quầy kính đối xứng).
- Biển thương hiệu: sau lưng toàn bộ object, áp tường bắc giữa bakery/deli,
  mặt +Z về camera (mẫu §9.3: trong mép đất, ngoài footprint hàng xóm).

## 3. Camera + nhãn

- Indoor → home riêng: từ nam cao nhìn chếch bắc
  (`pos [0, 9, 20], look [0, 1.5, -4]`) — đứng xa là tường bắc dồn pill (§10.1).
- Tối đa 3–4 nhãn mỗi tường: lịch/ưu đãi treo rời tường ra chân đứng riêng;
  biển coupon/discount treo trần bằng dây (có trụ neo — §12.6: vật treo phải
  có điểm đỡ, ở đây là ray trần decor).
- Kệ cao 2 m: nhãn trên nóc kệ, mũi tên dư 0.05 trên 0.8 (§9.9). Đồ trên mặt
  quầy: đáy lút 0.005. Mặt kính tủ đông/quầy deli: một `GlassPane` chung +
  tắt raycast, khung lút vào kính (§10.5).
- `cart` patrol aisle giữa (x 0, z −4..6, né pill quầy promotion ≥1 m);
  nhãn treo cao trên thân xe (§7.5). `cashier` đứng yên sau quầy (Person,
  mặt +X rồi xoay về camera).
- Nhãn kệ dài: `focus` vào giữa dãy (§types: bay tới đầu thì chỉ thấy đầu).
