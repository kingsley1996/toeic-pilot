"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";

/** Chép mẫu định dạng dán của từng part vào clipboard. */

export function CopyFormatButton({ template, part }: { template: string; part: number }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  /*
   * Sao chép CHÍNH chuỗi đang làm placeholder, không phải một bản mẫu viết
   * riêng: hai chuỗi mô tả cùng một định dạng thì sẽ lệch nhau, và bản lệch là
   * bản người ta dán vào — trong khi bản đúng là bản họ chỉ nhìn thấy mờ mờ.
   */
  async function copy() {
    try {
      // `navigator.clipboard` chỉ tồn tại ở secure context. Thiếu nó thì phải
      // NÓI RA chứ không im lặng không làm gì — cùng bài học với trình dán trả
      // về 0 cụm và 0 lỗi.
      if (!navigator.clipboard) throw new Error("no clipboard");
      // Chạy đua với đồng hồ, vì `writeText` có thể **không bao giờ settle**:
      // khi trình duyệt chặn (thiếu user activation, hoặc đang chờ một hộp xin
      // quyền không hiện ra), promise treo vô hạn. Không có nhánh nào chạy,
      // nút đứng im, và người dùng bấm lại vài lần rồi bỏ cuộc — đúng kiểu im
      // lặng mà trình dán vừa phải sửa. Đã gặp thật khi kiểm bằng trình duyệt.
      await Promise.race([
        navigator.clipboard.writeText(template),
        new Promise((_, reject) => window.setTimeout(() => reject(new Error("timeout")), 1500)),
      ]);
      setState("copied");
      window.setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("failed");
      window.setTimeout(() => setState("idle"), 4000);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {state === "failed" && (
        <span className="text-small text-alert">Trình duyệt chặn — bấm vào ô mẫu rồi copy tay</span>
      )}
      <Button
        size="sm"
        variant="quiet"
        onClick={() => void copy()}
        title={`Chép mẫu định dạng Part ${part} vào clipboard`}
      >
        {state === "copied" ? (
          <>
            <Check size={14} strokeWidth={2} aria-hidden />
            Đã chép
          </>
        ) : (
          <>
            <Copy size={14} strokeWidth={2} aria-hidden />
            Chép mẫu
          </>
        )}
      </Button>
    </div>
  );
}
