"use client";

import { type LlmStats } from "@toeic-pilot/shared";

import { Panel } from "@/components/ui";

/**
 * Độ đúng của máy, tính RIÊNG cho từng mặt phân loại.
 *
 * Một con số gộp cho cả sáu mặt che mất thứ quyết định phải sửa prompt nào: máy
 * có thể đoán rất tốt dạng câu hỏi mà rất tệ điểm ngữ pháp, và "trung bình 80%"
 * không nói được điều đó.
 *
 * Không còn cột cảnh báo ngưỡng như bộ nhãn cũ. Ngưỡng "nhãn nhỏ nhất ≥5%" được
 * hiệu chỉnh cho 6–8 nhãn; với 72 mã thì mọi mã đều dưới 5% và cột ấy sẽ đỏ
 * toàn bộ — một cảnh báo luôn bật là một cảnh báo không ai đọc.
 */
export function FacetAccuracyTable({ facets }: { facets: LlmStats["facets"] }) {
  if (facets.length === 0) {
    return <Panel className="text-small text-ink-muted">Chưa có nhãn nào.</Panel>;
  }
  return (
    <Panel className="overflow-x-auto p-0">
      <table className="w-full min-w-[520px] text-small">
        <thead>
          <tr className="border-b border-rule-strong text-label uppercase text-ink-faint">
            <th className="whitespace-nowrap px-4 py-2.5 text-left font-semibold">Mặt phân loại</th>
            <th className="whitespace-nowrap px-4 py-2.5 text-right font-semibold">Đã gắn</th>
            <th className="whitespace-nowrap px-4 py-2.5 text-right font-semibold">Đã kiểm</th>
            <th className="whitespace-nowrap px-4 py-2.5 text-right font-semibold">Máy đúng</th>
          </tr>
        </thead>
        <tbody>
          {facets.map((facet) => {
            const rate = facet.reviewed > 0 ? facet.agreeing / facet.reviewed : null;
            return (
              <tr key={facet.facet} className="border-b border-rule last:border-0">
                <td className="px-4 py-2.5">
                  <div className="font-semibold">{facet.label_vi}</div>
                  <div className="font-data text-label text-ink-faint">{facet.facet}</div>
                </td>
                <td className="px-4 py-2.5 text-right font-data tabular-nums">{facet.labelled}</td>
                <td className="px-4 py-2.5 text-right font-data tabular-nums">{facet.reviewed}</td>
                <td className="px-4 py-2.5 text-right font-data tabular-nums">
                  {/*
                   * "—" khi chưa ai kiểm, KHÔNG phải 0%. Chúng là hai chuyện
                   * khác hẳn nhau: một bên là chưa đo, một bên là đo rồi và máy
                   * sai hết. Hiện 0% cho trường hợp đầu là báo cáo một kết quả
                   * chưa từng tồn tại.
                   */}
                  {rate === null ? (
                    <span className="text-ink-faint">—</span>
                  ) : (
                    <span className={rate >= 0.9 ? "text-ok" : "text-warn"}>
                      {(rate * 100).toFixed(0)}%
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
