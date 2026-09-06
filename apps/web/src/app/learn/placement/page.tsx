"use client";

import { API_ROUTES, type PlacementGate } from "@toeic-pilot/shared";
import { ArrowRight, FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Input,
  Page,
  PageHeader,
  Panel,
  SkeletonList,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Bài test đầu vào — 84 câu rút từ đề mẫu, ~50 phút (SPEC-PLACEMENT).
 *
 * Điểm tự khai TRƯỚC bài là mốc so sánh, không phải dữ liệu chấm: người từng
 * thi thật có một con số để đối chiếu với ước lượng; chưa từng thi thì bỏ trống.
 */
export default function PlacementSetupPage() {
  const router = useRouter();
  const { status, token } = useRequireSession();
  const [gate, setGate] = useState<PlacementGate | null>(null);
  const [selfScore, setSelfScore] = useState("");
  const [targetScore, setTargetScore] = useState("");
  const [examDate, setExamDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<PlacementGate>(API_ROUTES.placementGate, { token })
      .then((g) => {
        setGate(g);
        // Prefill từ hồ sơ — một nguồn sự thật: giá trị cũ hiện sẵn, đổi thì
        // submit ghi về lại profile.
        if (g.profile_target_score !== null) setTargetScore(String(g.profile_target_score));
        if (g.profile_exam_date) setExamDate(g.profile_exam_date);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không tải được trạng thái bài test."),
      );
  }, [token]);

  async function start() {
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    try {
      const g = await apiFetch<PlacementGate>(API_ROUTES.placementStart, {
        method: "POST",
        token,
        body: JSON.stringify({
          self_reported_score: selfScore ? Number(selfScore) : null,
          target_score: targetScore ? Number(targetScore) : null,
          exam_date: examDate || null,
        }),
      });
      router.push(`/learn/attempts/${g.in_progress_attempt_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không mở được bài test.");
      setBusy(false);
    }
  }

  if (status !== "authenticated") {
    return (
      <Page className="max-w-2xl">
        <SkeletonList rows={3} />
      </Page>
    );
  }

  const inProgress = gate?.in_progress_attempt_id ?? null;

  return (
    <Page className="max-w-2xl">
      <PageHeader
        eyebrow="Bài test đầu vào"
        title="Xác định trình độ của bạn"
        description="84 câu theo đủ bảy phần, khoảng 50 phút. Kết quả là trình độ ước lượng (CEFR), dải điểm TOEIC ước tính, và những kỹ năng nên luyện trước."
      />

      {error && (
        <div className="mb-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      {!gate && <SkeletonList rows={3} />}

      {gate && inProgress && (
        <Panel className="mt-6 p-5">
          <p className="font-semibold">Bạn có lượt bài test đang làm dở.</p>
          <p className="mt-1 text-small text-ink-muted">
            Đồng hồ vẫn chạy ở máy chủ — mở lại để làm tiếp trước khi hết giờ.
          </p>
          <div className="mt-3">
            <ButtonLink href={`/learn/attempts/${inProgress}`}>Tiếp tục lượt đang làm</ButtonLink>
          </div>
        </Panel>
      )}

      {gate && !inProgress && !gate.can_start && (
        <div className="mt-6">
          <EmptyState
            icon={FileText}
            title="Bài test đầu vào làm mỗi tuần một lần"
            description={
              gate.next_available_at
                ? `Bạn có thể làm lại từ ${new Date(gate.next_available_at).toLocaleDateString("vi-VN")}.`
                : "Hãy quay lại sau."
            }
            action={<ButtonLink href="/dashboard">Về trang học</ButtonLink>}
          />
        </div>
      )}

      {gate && !inProgress && gate.can_start && (
        <Panel className="mt-6 p-5">
          <p className="text-label font-semibold uppercase text-ink-faint">
            Mục tiêu ôn thi (không bắt buộc)
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Input
              value={selfScore}
              onChange={(e) => setSelfScore(e.target.value)}
              type="number"
              min={10}
              max={990}
              placeholder="Điểm TOEIC hiện tại"
              aria-label="Điểm TOEIC hiện tại"
            />
            <Input
              value={targetScore}
              onChange={(e) => setTargetScore(e.target.value)}
              type="number"
              min={10}
              max={990}
              placeholder="Điểm mục tiêu"
              aria-label="Điểm mục tiêu"
            />
          </div>
          <div className="mt-3">
            <Input
              value={examDate}
              onChange={(e) => setExamDate(e.target.value)}
              type="date"
              min={new Date().toISOString().slice(0, 10)}
              aria-label="Ngày thi dự kiến"
            />
          </div>
          <p className="mt-2 text-small text-ink-muted">
            Điểm mục tiêu và ngày thi dự kiến là mục tiêu ôn thi của bạn — kế hoạch học dùng chúng
            để xếp lịch. Đổi ở đây cũng cập nhật hồ sơ.
          </p>

          <div className="mt-5">
            <Button size="lg" className="w-full" disabled={busy} onClick={() => void start()}>
              {busy ? "Đang mở bài…" : "Bắt đầu bài test"}
              <ArrowRight size={15} strokeWidth={2} className="ml-1.5" aria-hidden />
            </Button>
            <p className="mt-2 text-center text-small text-ink-muted">
              Đồng hồ 50 phút chạy ở máy chủ — hết giờ là tự nộp.
            </p>
          </div>
        </Panel>
      )}
    </Page>
  );
}
