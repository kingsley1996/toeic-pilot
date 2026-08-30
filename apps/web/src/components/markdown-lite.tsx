import type { ReactNode } from "react";

import { cx } from "@/components/ui";

/**
 * Markdown TỐI GIẢN cho bong bóng chat — đủ cho những gì model thực sự trả ra:
 * **đậm**, `code`, gạch đầu dòng `- `, xuống dòng, và trích dẫn `[ref]`.
 *
 * Vì sao không phải `react-markdown`: bong bóng chat chỉ cần một tập con nhỏ,
 * và thêm một dependency + cây parser đầy đủ cho bốn quy tắc là đúng kiểu
 * phình mà dự án này luôn cắt. Vì sao không phải regex → chuỗi HTML: mọi thứ
 * ở dưới là React node với text thẳng, nên chữ người dùng/model KHÔNG BAO GIỜ
 * thành HTML — một `dangerouslySetInnerHTML` ở đây là đường XSS ngắn nhất có
 * thể, kể cả khi đầu vào "chỉ" là của model.
 *
 * Vòng đời của một câu trả lời sai format trước bản này: model trả markdown
 * (điều nó LUÔN làm, prompt chặn cũng chỉ chặn được phần lớn), bong bóng in
 * nguyên dấu `**`, gộp cả danh sách vào một dòng — trông như hỏng chứ không
 * như lỗi render. Renderer chịu mọi nhà cung cấp, không phụ thuộc prompt.
 */

const BOLD_OR_CODE_OR_REF = /(\*\*[^*]+\*\*|`[^`]+`|\[[a-z0-9][a-z0-9-]*\])/g;

function inline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(BOLD_OR_CODE_OR_REF).map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={key} className="font-mono text-[0.85em] text-ink">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (/^\[[a-z0-9][a-z0-9-]*\]$/.test(part)) {
      // Trích dẫn tài liệu của Trợ lý — mờ đi vì nó là dẫn chứng, không phải
      // nội dung: người đọc liếc thấy là có nguồn, không mất nhịp đọc.
      return (
        <span key={key} className="text-ink-faint">
          {part}
        </span>
      );
    }
    return part;
  });
}

export function MarkdownLite({ text, className }: { text: string; className?: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];

  const flushBullets = () => {
    if (bullets.length === 0) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="ml-4 list-disc space-y-1">
        {bullets.map((item, index) => (
          <li key={index}>{inline(item, `li-${blocks.length}-${index}`)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  lines.forEach((raw, index) => {
    const line = raw.trimEnd();
    if (line.startsWith("- ")) {
      bullets.push(line.slice(2));
      return;
    }
    flushBullets();
    if (line.trim() !== "") {
      blocks.push(<p key={`p-${index}`}>{inline(line, `p-${index}`)}</p>);
    }
  });
  flushBullets();

  return <div className={cx("space-y-1.5", className)}>{blocks}</div>;
}
