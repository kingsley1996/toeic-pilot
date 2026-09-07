"use client";

import { API_ROUTES, type PlacementResultPublic } from "@toeic-pilot/shared";
import { CheckCircle2, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, ButtonLink, Page, PageHeader, Panel, SkeletonList, cx } from "@/components/ui";
import { formatDuration } from "@/app/learn/attempts/[attemptId]/_components/shared";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Phân tích bài test đầu vào — phán quyết của server (SPEC-PLACEMENT §2–§3).
 *
 * Dải điểm và băng CEFR là ƯỚC LƯỢNG từ đề 84 câu (CI 95%); UI luôn nói ra
 * điều đó. Trình độ tổng thể là section yếu hơn — bảo thủ một cách cố ý.
 */

const CEFR_VI: Record<string, string> = {
  A1: "A1 — Mới bắt đầu",
  A2: "A2 — Sơ cấp",
  B1: "B1 — Trung cấp",
  B2: "B2 — Trung cấp cao",
  C1: "C1 — Nâng cao (trần của TOEIC)",
};

export default function PlacementResultPage() {
  const params = useParams<{ attemptId: string }>();
  const { token } = useRequireSession();
  const [result, setResult] = useState<PlacementResultPublic | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!token || !params.attemptId) return;
    apiFetch<PlacementResultPublic>(API_ROUTES.placementAnalyze(params.attemptId), {
      method: "POST",
      token,
    })
      .then(setResult)
      .catch(() => setFailed(true));
  }, [token, params.attemptId]);

  if (failed) {
    return (
      <Page className="max-w-2xl">
        <Alert tone="alert">
          Không phân tích được bài này. Nếu bài chưa nộp, hãy nộp trước khi quay lại.
        </Alert>
      </Page>
    );
  }
  if (!result) {
    return (
      <Page className="max-w-2xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  const estMid = (low: number, high: number) => Math.round((low + high) / 2);
  const listeningMid = estMid(result.listening_band.low, result.listening_band.high);
  const readingMid = estMid(result.reading_band.low, result.reading_band.high);
  const estimatedTotal = listeningMid + readingMid;

  return (
    <Page className="max-w-2xl">
      <PageHeader
        eyebrow="Bài test đầu vào"
        title="Trình độ hiện tại của bạn"
        description="Đây là ƯỚC LƯỢNG từ 84 câu — con số thật thay đổi theo từng bài luyện."
      />

      <Panel className="mt-6 p-6 text-center">
        <p className="font-data text-title font-semibold tabular-nums">{result.cefr_overall}</p>
        <p className="mt-1 font-semibold">{CEFR_VI[result.cefr_overall] ?? result.cefr_overall}</p>
        <p className="mt-2 text-small text-ink-muted">
          Tổng điểm TOEIC ước tính:{" "}
          <span className="font-data tabular-nums text-ink">{estimatedTotal}</span> / 990
        </p>
        <p className="mt-1 text-small text-ink-muted">
          Thời gian làm bài:{" "}
          <span className="font-data tabular-nums">{formatDuration(result.elapsed_seconds)}</span>
        </p>
      </Panel>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <SectionCard
          title="Nghe"
          raw={result.listening_raw}
          band={result.listening_band}
          cefr={result.cefr_listening}
        />
        <SectionCard
          title="Đọc"
          raw={result.reading_raw}
          band={result.reading_band}
          cefr={result.cefr_reading}
        />
      </div>

      {result.self_reported_score !== null && (
        <Panel className="mt-4 p-4">
          <p className="text-small">
            So với điểm bạn tự khai (
            <span className="font-data tabular-nums text-ink">{result.self_reported_score}</span>
            ):{" "}
            {estimatedTotal >= result.self_reported_score ? (
              <span className="font-semibold text-ok">ước lượng cao hơn</span>
            ) : (
              <span className="font-semibold text-alert">ước lượng thấp hơn</span>
            )}
            . Điểm thật trên đề 200 câu thường nằm trong dải ước lượng.
          </p>
        </Panel>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <SkillList
          title="Điểm mạnh"
          Icon={TrendingUp}
          tone="ok"
          skills={result.strengths}
          empty="Chưa đủ dữ liệu để gọi là điểm mạnh — luyện thêm rồi quay lại."
        />
        <SkillList
          title="Nên luyện trước"
          Icon={TrendingDown}
          tone="alert"
          skills={result.weaknesses}
          empty="Không có kỹ năng nào yếu rõ rệt. Duy trì nhịp luyện hiện tại."
        />
      </div>

      <div className="mt-8 flex flex-wrap gap-3 border-t border-rule pt-5">
        <ButtonLink href={`/learn/plan?from=${result.attempt_id}`}>Tạo kế hoạch học</ButtonLink>
        {/* Xem lại từng câu dùng lại màn làm bài của đề thi thử: GET
            /attempts/{id} trả đáp án đã chấm cho mọi đề đã nộp, không riêng đề
            200 câu — chỉ bảng điểm quy đổi mới không áp dụng cho đề 84 câu. */}
        <ButtonLink href={`/learn/attempts/${result.attempt_id}`} variant="secondary">
          Xem lại bài làm
        </ButtonLink>
        <ButtonLink href="/learn/parts" variant="secondary">
          Luyện theo phần
        </ButtonLink>
        <Link
          href="/dashboard"
          className="inline-flex items-center rounded px-4 py-2 text-small font-semibold text-ink-muted hover:text-ink"
        >
          Về trang học
        </Link>
      </div>
    </Page>
  );
}

function SectionCard({
  title,
  raw,
  band,
  cefr,
}: {
  title: string;
  raw: number;
  band: { low: number; high: number };
  cefr: string;
}) {
  return (
    <Panel className="p-4">
      <p className="font-semibold">{title}</p>
      <p className="mt-2 font-data text-subtitle font-semibold tabular-nums">
        {band.low}–{band.high}
        <span className="ml-1 text-small font-normal text-ink-muted">điểm ước tính</span>
      </p>
      <p className="mt-1 text-small text-ink-muted">
        {CEFR_VI[cefr] ?? cefr} · đúng {raw} câu
      </p>
    </Panel>
  );
}

function SkillList({
  title,
  Icon,
  tone,
  skills,
  empty,
}: {
  title: string;
  Icon: typeof TrendingUp;
  tone: "ok" | "alert";
  skills: string[];
  empty: string;
}) {
  return (
    <Panel className="p-4">
      <p className="flex items-center gap-2 font-semibold">
        <Icon
          size={15}
          strokeWidth={2}
          className={tone === "ok" ? "text-ok" : "text-alert"}
          aria-hidden
        />
        {title}
      </p>
      {skills.length === 0 ? (
        <p className="mt-2 text-small text-ink-muted">{empty}</p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {skills.map((s) => (
            <li key={s} className="flex items-start gap-2 text-small">
              <CheckCircle2
                size={14}
                strokeWidth={2}
                className={cx("mt-0.5 shrink-0", tone === "ok" ? "text-ok" : "text-alert")}
                aria-hidden
              />
              {s}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
