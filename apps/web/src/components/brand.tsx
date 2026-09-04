/**
 * Dấu hiệu thương hiệu, một định nghĩa cho cả ba chỗ dùng nó.
 *
 * Trước đây nó là ô cam chữ **T**, chép nguyên văn ba lần — hai lần trong
 * `shell.tsx` (thanh trên và sidebar) và một lần ở chân trang. Ba bản chép của
 * cùng một dấu hiệu là ba chỗ phải nhớ sửa cùng lúc, và lần này chính là lần
 * chứng minh: đổi nó nghĩa là đi tìm cho đủ ba.
 *
 * Chữ T là chỗ tạm và nó **không nhắc gì tới con mascot** đang đứng ở landing,
 * ở trang đăng ký và giờ là ở icon trình duyệt. Thay bằng chính con phi công ấy
 * thì cả sản phẩm nói một ngôn ngữ hình ảnh.
 *
 * Ảnh cắt sát hơn `icon.png`: bản kia chừa lề rộng vì iOS và Android tự bo góc
 * và tự thêm nền, còn ở đây 28 pixel nào cũng đắt — giữ nguyên lề ấy thì cái
 * đầu chỉ còn 19px. Nguồn 128px là đủ cho 28px trên màn hình 4×.
 *
 * `<img>` thường, không phải `next/image`: đây là tài sản tĩnh trong `public/`,
 * kích thước cố định, và bộ tối ưu không có gì để tối ưu ở một tệp 18 KB.
 */
export function BrandMark() {
  return (
    /* Bo 4px, đúng bán kính duy nhất của hệ thiết kế — cùng hình dạng mà ô cam
       chữ T đã có, nên chỗ nó đứng trong bố cục không đổi. */
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/brand/mark.png"
      alt=""
      aria-hidden
      width={28}
      height={28}
      className="h-7 w-7 shrink-0 rounded"
    />
  );
}
