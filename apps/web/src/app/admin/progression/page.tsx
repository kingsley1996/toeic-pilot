"use client";

import { API_ROUTES, type ProgressionConfigAdmin } from "@toeic-pilot/shared";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, Page, PageHeader, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { messageFor, uploadProgressionArt } from "@/lib/upload";
import { useRequireSession } from "@/lib/session";
import { BadgesSection } from "./_components/badges-section";
import { CurveSection } from "./_components/curve-section";
import { FramesSection } from "./_components/frames-section";
import { RatesSection } from "./_components/rates-section";
import { SlotsSection } from "./_components/slots-section";

/**
 * Progression controls: XP rates, the daily cap, the level curve, avatar frames
 * and badge rules.
 *
 * Everything on this page used to be a constant in the API. Three properties of
 * the underlying design are what make it safe to hand over, and each one fails
 * silently if a later change gives it up:
 *
 *   · **XP is a ledger.** Every `xp_event` row stores the amount granted at the
 *     time, so lowering a rate today never claws back points somebody already
 *     earned. That is the whole reason the rates are editable at all.
 *   · **Level never drops.** `user_profile.level_reached` is a high-water mark,
 *     so raising the curve slows down new learners without taking a level away
 *     from anyone who already reached it.
 *   · **A daily task slot is a row with a stable uuid**, and that uuid is what
 *     the anti-double-award constraint keys on. Rename a slot, move its target,
 *     change its reward — the days already paid stay paid. Deleting a slot and
 *     recreating "the same" one does not: the new row is a new uuid, and every
 *     past day becomes unpaid again. Disable rather than delete.
 *
 * Every write here returns the whole configuration, so the screen replaces its
 * state with what the server actually stored instead of guessing.
 */

export default function ProgressionAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  /*
   * MỘT bản nháp cho cả trang, không phải một bản sao trong mỗi hàng.
   *
   * Mỗi hàng giữ state riêng thì phải đồng bộ lại mỗi khi máy chủ trả về cấu
   * hình mới, và cách duy nhất để làm điều đó là `setState` trong một effect —
   * thứ mà `react-hooks/set-state-in-effect` cấm, vì nó xếp tầng render và trôi
   * khỏi dữ liệu nó mô tả. Ở đây các hàng là component có kiểm soát: chúng chỉ
   * nhận `value` và `onChange`, còn sự thật thì nằm một chỗ.
   */
  const [config, setConfig] = useState<ProgressionConfigAdmin | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    apiFetch<ProgressionConfigAdmin>(API_ROUTES.adminProgression, { token })
      .then(setConfig)
      .catch(() => setError("Could not load the configuration."));
  }, [token]);

  /**
   * Every mutation goes through here.
   *
   * `await` is on its own line on purpose: `done?.(await work())` short-circuits
   * the *whole* call expression when `done` is nullish, so the work never runs
   * and the caller is told it succeeded. That cost this project a long hunt once
   * already (CLAUDE.md).
   */
  async function send(path: string, method: string, body?: unknown) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiFetch<ProgressionConfigAdmin>(path, {
        method,
        token,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      setConfig(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  /** Tải một file lên, trả về khoá — hoặc `null` nếu hỏng (lỗi đã hiện ra). */
  async function upload(file: File): Promise<string | null> {
    if (!token) return null;
    setBusy(true);
    setError(null);
    try {
      // `await` trên dòng riêng, không nhét vào tham số của một lời gọi tuỳ chọn.
      const key = await uploadProgressionArt(file, token);
      return key;
    } catch (caught) {
      setError(messageFor(caught, "Could not upload the image."));
      return null;
    } finally {
      setBusy(false);
    }
  }

  if (status !== "authenticated" || !config) {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-6 h-64" />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Progression"
        title="XP, levels and badges"
        description="Applies to every learner from now on. Points already awarded are never recalculated, and nobody loses a level they have reached."
        actions={
          <>
            {/* Khung là thứ DUY NHẤT ở trang này không kiểm được bằng số liệu:
                tranh tràn ra ngoài ô 25% mỗi phía, nên phải nhìn. */}
            <Link
              href="/admin/progression/preview"
              className="text-small font-semibold text-ink-muted hover:text-ink"
            >
              Frame preview
            </Link>
            <Tag tone="warn">Admin only</Tag>
          </>
        }
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <RatesSection config={config} setConfig={setConfig} busy={busy} send={send} upload={upload} />
      <CurveSection config={config} setConfig={setConfig} busy={busy} send={send} upload={upload} />
      <SlotsSection config={config} setConfig={setConfig} busy={busy} send={send} upload={upload} />
      <FramesSection
        config={config}
        setConfig={setConfig}
        busy={busy}
        send={send}
        upload={upload}
      />
      <BadgesSection
        config={config}
        setConfig={setConfig}
        busy={busy}
        send={send}
        upload={upload}
      />
    </Page>
  );
}
