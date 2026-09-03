/**
 * Một tiếng reo: màn học báo cho con thú biết người học vừa trả lời đúng.
 *
 * Góc thú cưng sống ở `app-shell`, còn các màn học là những cây component khác
 * hẳn — không có prop nào nối hai bên, và luồn một prop qua sáu tầng chỉ để nói
 * "vừa đúng một câu" là cách chắc chắn nhất khiến lần thêm màn học sau quên mất
 * nó. Nên đây là một kênh phát, cùng khuôn `theme.ts` và `sidebar.ts`.
 *
 * **Sự kiện chứ không phải trạng thái**, nên không có `getSnapshot` và không
 * dùng `useSyncExternalStore`: không có giá trị nào để đọc, chỉ có một khoảnh
 * khắc để phản ứng. Ai nghe thì nghe, không ai nghe cũng không sao — góc thú
 * cưng vắng mặt ở màn làm bài là chuyện cố ý.
 *
 * `planning/docs/toeic_pilot_tamagotchi_mechanics.md` §22: trả lời đúng thì con
 * thú nhảy lên và loé sáng. Trả lời SAI thì tài liệu nói rõ **không** được mắng
 * — nên ở đây chỉ có một hàm, và nó chỉ dành cho lúc đúng.
 */

const listeners = new Set<() => void>();

/** Nghe tiếng reo. Trả về hàm huỷ đăng ký. */
export function subscribeToCheer(onCheer: () => void): () => void {
  listeners.add(onCheer);
  return () => {
    listeners.delete(onCheer);
  };
}

/** Người học vừa trả lời đúng một câu. */
export function cheer(): void {
  for (const listener of listeners) listener();
}
