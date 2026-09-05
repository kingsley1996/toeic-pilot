import type { ReactNode } from "react";

import { cx } from "@/components/ui";

/**
 * Markdown TỐI GIẢN — đủ cho bong bóng chat VÀ bài học ngữ pháp: **đậm**,
 * *nghiêng*, ~~gạch~~, <u>gạch chân</u>, `code`, gạch đầu dòng `- `, xuống dòng,
 * trích dẫn `[ref]`, tiêu đề `#`→`####`, blockquote `> `, phân cách `---`, bảng
 * `| ... |` (dòng `|---|` bị bỏ), và `<br>`/`<u>` thành ngắt dòng/gạch chân.
 *
 * Vì sao không phải `react-markdown`: chỉ cần một tập con nhỏ, và thêm một
 * dependency + cây parser đầy đủ cho vài quy tắc là đúng kiểu phình mà dự án
 * này luôn cắt. Vì sao không phải regex → chuỗi HTML: mọi thứ ở dưới là React
 * node với text thẳng, nên chữ người dùng/model KHÔNG BAO GIỜ thành HTML — một
 * `dangerouslySetInnerHTML` ở đây là đường XSS ngắn nhất có thể, kể cả khi đầu
 * vào "chỉ" là của model. `<br>` được nhận DIỆN DANH như một quy tắc và biến
 * thành React `<br/>`, không phải bằng cách cho phép HTML chui qua.
 *
 * Bảng vào cùng lúc với bài học ngữ pháp (`SPEC-GRAMMAR.md` §5): bảng chia thì
 * là dạng nội dung hiển nhiên nhất của giáo trình. Đổi lại cái giá đã ghi ở spec:
 * cú pháp viết sai hiện ra SAI chứ không nổ — nên màn soạn có ô xem trước.
 *
 * Vòng đời của một câu trả lời sai format trước bản này: model trả markdown
 * (điều nó LUÔN làm, prompt chặn cũng chỉ chặn được phần lớn), bong bóng in
 * nguyên dấu `**`, gộp cả danh sách vào một dòng — trông như hỏng chứ không
 * như lỗi render. Renderer chịu mọi nhà cung cấp, không phụ thuộc prompt.
 */

const BR_TAG = /<br\s*\/?>/i;

function inline(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  text
    .split(/(<u>[^<]+<\/u>|\*\*[^*]+\*\*|~~[^~]+~~|\*[^*]+\*|`[^`]+`|\[[a-z0-9][a-z0-9-]*\])/g)
    .forEach((part, index) => {
      const key = `${keyPrefix}-${index}`;
      // `<u>` đứng TRƯỚC nhánh đậm trong alternation: ngược lại thì
      // `<u>**x**</u>` bị tách làm đôi và hai thẻ trần sót lại thành chữ.
      // Bên trong vẫn chạy `inline` để giữ đậm/nghiêng lồng nhau.
      if (part.startsWith("<u>") && part.endsWith("</u>") && part.length > 7) {
        out.push(<u key={key}>{inline(part.slice(3, -4), `${key}-u`)}</u>);
        return;
      }
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        out.push(<strong key={key}>{part.slice(2, -2)}</strong>);
        return;
      }
      if (part.startsWith("~~") && part.endsWith("~~") && part.length > 4) {
        out.push(
          <s key={key} className="text-ink-faint">
            {part.slice(2, -2)}
          </s>,
        );
        return;
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        out.push(<em key={key}>{part.slice(1, -1)}</em>);
        return;
      }
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
        out.push(
          <code key={key} className="font-mono text-[0.85em] text-ink">
            {part.slice(1, -1)}
          </code>,
        );
        return;
      }
      if (/^\[[a-z0-9][a-z0-9-]*\]$/.test(part)) {
        // Trích dẫn tài liệu của Trợ lý — mờ đi vì nó là dẫn chứng, không phải
        // nội dung: người đọc liếc thấy là có nguồn, không mất nhịp đọc.
        out.push(
          <span key={key} className="text-ink-faint">
            {part}
          </span>,
        );
        return;
      }
      // Text thường: duy nhất thứ được nhận là `<br>` — giáo trình dùng nó trong
      // ô bảng để xếp nhiều ví dụ một hàng. Key phải mang cả `segIndex`: một ô
      // có ba `<br>` là ba segment, và key không có số thứ tự thì trùng nhau —
      // React cảnh báo "two children with the same key" ngay trên trang bài học.
      const segments = part.split(BR_TAG);
      segments.forEach((segment, segIndex) => {
        if (segment !== "")
          out.push(segIndex === 0 ? segment : <span key={`${key}-t${segIndex}`}>{segment}</span>);
        if (segIndex < segments.length - 1) out.push(<br key={`${key}-br${segIndex}`} />);
      });
    });
  return out;
}

function tableBlock(rows: string[][], key: string): ReactNode {
  const header = rows[0];
  const body = rows.slice(1);
  return (
    <table key={key} className="w-full border-collapse text-small">
      <thead>
        <tr>
          {header.map((cell, index) => (
            <th key={index} className="border border-rule-strong px-2 py-1 text-left font-semibold">
              {inline(cell, `th-${key}-${index}`)}
            </th>
          ))}
        </tr>
      </thead>
      {body.length > 0 && (
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {header.map((_, colIndex) => (
                // Hàng ngắn hơn header: ô trống, không phải lỗi — hàng thừa thì
                // bị bỏ, vì không còn cột nào để rơi vào.
                <td key={colIndex} className="border border-rule px-2 py-1">
                  {inline(row[colIndex] ?? "", `td-${key}-${rowIndex}-${colIndex}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      )}
    </table>
  );
}

const TABLE_SEPARATOR = /^\|?\s*:?-{2,}.*\|/;

function splitRow(line: string): string[] {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

export function MarkdownLite({ text, className }: { text: string; className?: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];
  let tableRows: string[][] = [];
  let quotes: string[] = [];

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

  const flushTable = () => {
    if (tableRows.length === 0) return;
    blocks.push(tableBlock(tableRows, `table-${blocks.length}`));
    tableRows = [];
  };

  const flushQuote = () => {
    if (quotes.length === 0) return;
    blocks.push(
      <blockquote
        key={`bq-${blocks.length}`}
        className="border-l-2 border-rule-strong pl-4 text-ink-muted"
      >
        {quotes.map((line, index) => (
          <p key={index}>{inline(line, `bq-${blocks.length}-${index}`)}</p>
        ))}
      </blockquote>,
    );
    quotes = [];
  };

  const flushAll = () => {
    flushBullets();
    flushTable();
    flushQuote();
  };

  lines.forEach((raw, index) => {
    const line = raw.trimEnd();
    if (line.startsWith("- ")) {
      flushTable();
      flushQuote();
      bullets.push(line.slice(2));
      return;
    }
    if (line.trim().startsWith("|")) {
      flushBullets();
      flushQuote();
      const cells = splitRow(line.trim());
      // Dòng phân cách `|---|---|` không mang nội dung — header là dòng trước nó.
      if (!TABLE_SEPARATOR.test(line.trim())) tableRows.push(cells);
      return;
    }
    flushAll();
    if (line.startsWith("> ")) {
      quotes.push(line.slice(2));
      return;
    }
    if (line.trim() === "---" || line.trim() === "***") {
      blocks.push(<hr key={`hr-${index}`} className="border-0 border-t border-rule" />);
      return;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const content = inline(heading[2], `h-${index}`);
      // Phân cấp bằng CỠ TƯƠNG ĐỐI (em) chứ không absolute: cùng một tệp render
      // trong bong bóng chat 13px và trang học 16px — absolute sẽ làm tiêu đề
      // tài liệu nhỏ hơn thân bài. `pt` (padding, không margin) vì `space-y`
      // của khối cha thắng margin trên phần tử con; padding thì không ai cãi.
      blocks.push(
        level === 1 ? (
          <h2 key={`h-${index}`} className="pt-5 text-subtitle font-semibold">
            {content}
          </h2>
        ) : level === 2 ? (
          <h3 key={`h-${index}`} className="pt-4 text-[1.15em] leading-snug font-semibold">
            {content}
          </h3>
        ) : level === 3 ? (
          <h4 key={`h-${index}`} className="pt-3 text-[1.05em] font-semibold">
            {content}
          </h4>
        ) : (
          <h5 key={`h-${index}`} className="pt-2 text-[0.95em] font-semibold text-ink-muted">
            {content}
          </h5>
        ),
      );
      return;
    }
    if (line.trim() !== "") {
      blocks.push(<p key={`p-${index}`}>{inline(line, `p-${index}`)}</p>);
    }
  });
  flushAll();

  return <div className={cx("space-y-1.5", className)}>{blocks}</div>;
}
