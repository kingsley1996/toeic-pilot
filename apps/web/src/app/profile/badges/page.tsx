"use client";

import { API_ROUTES, type BadgesPublic } from "@toeic-pilot/shared";
import { useEffect, useRef, useState } from "react";

import { BadgeTile } from "@/components/badges";
import { Page, PageHeader, Panel, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Trang huy hiệu.
 *
 * Hiện CẢ huy hiệu chưa mở, kèm tiến độ: một trang chỉ trưng thứ đã đạt thì
 * không nói được còn gì phía trước, mà đó mới là thứ khiến người ta quay lại.
 *
 * **Chấm đỏ tắt ở đây, sau khi trang đã dựng xong.** `POST .../seen` gọi sau khi
 * đã giữ lại danh sách "mới" trong `newCodes`, nên nhãn MỚI vẫn hiện trong đúng
 * lượt xem này rồi mới biến mất ở lần sau. Gọi trước khi dựng thì người dùng mở
 * trang ra và không thấy cái nào mới cả — tức là thông báo đã dẫn họ tới một
 * trang không nói gì thêm.
 */
export default function BadgesPage() {
  const { status, token } = useRequireSession();
  const [data, setData] = useState<BadgesPublic | null>(null);
  /* Chụp lại lúc đọc xong. State riêng chứ không đọc `badge.seen` khi vẽ: lệnh
     đánh dấu chạy ngay sau đó, và nếu về sau ai đó cho trang đọc lại thì nhãn
     MỚI sẽ biến mất giữa lượt xem. */
  const [newCodes, setNewCodes] = useState<Set<string>>(new Set());
  // Đánh dấu đúng MỘT lần cho mỗi lần mở trang. React ở chế độ nghiêm ngặt chạy
  // effect hai lần lúc dựng, và lần thứ hai không được biến thành một request
  // thứ hai — nó vô hại (204 và không có gì để đánh dấu) nhưng vẫn là tiếng ồn.
  const marked = useRef(false);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    apiFetch<BadgesPublic>(API_ROUTES.badges, { token })
      .then((value) => {
        if (!alive) return;
        setData(value);
        setNewCodes(new Set(value.badges.filter((b) => b.earned && !b.seen).map((b) => b.code)));
        if (value.unseen_count > 0 && !marked.current) {
          marked.current = true;
          // 204 → `apiFetch` trả `undefined`; ở đây không cần gì hơn thế.
          void apiFetch<void>(API_ROUTES.badgesSeen, { method: "POST", token }).catch(() => {});
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token]);

  if (status !== "authenticated") {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-8 h-64" />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Hồ sơ"
        title="Huy hiệu"
        /* Bất đối xứng ở USER-ROAD §0 phải được NÓI RA, không để người dùng tự
           suy: huy hiệu tính cả quá khứ còn XP thì bắt đầu từ 0, nên một người
           đã học lâu sẽ thấy "300 từ" ngay trong khi vẫn ở level 1. Không giải
           thích thì nó đọc thành lỗi. */
        description="Huy hiệu tính cả quãng đường bạn đã học từ trước. XP và level thì bắt đầu từ 0 khi tính năng này ra mắt, nên bạn có thể mở được huy hiệu lớn trong lúc level vẫn còn thấp."
        actions={
          data && (
            <Tag tone={data.earned_count > 0 ? "action" : "neutral"}>
              {data.earned_count}/{data.badges.length}
            </Tag>
          )
        }
      />

      {data === null ? (
        <Skeleton className="h-64" />
      ) : (
        <Panel className="p-5 sm:p-6">
          <ul className="grid gap-3 sm:grid-cols-2">
            {data.badges.map((badge) => (
              <BadgeTile key={badge.code} badge={badge} isNew={newCodes.has(badge.code)} />
            ))}
          </ul>
        </Panel>
      )}
    </Page>
  );
}
