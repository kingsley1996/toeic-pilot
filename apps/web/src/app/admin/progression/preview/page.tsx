"use client";

import { API_ROUTES, type FramePublic, type ProgressionConfigAdmin } from "@toeic-pilot/shared";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, Avatar, Button, Page, PageHeader, Panel, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Every avatar frame, rendered by the real `Avatar` component.
 *
 * This screen exists because frame art is the one part of the progression
 * feature that **cannot be checked from the terminal**. The API can say a row
 * has an `image_url` and the CDN can return 200 while the frame still sits
 * wrong: art overflows its box by 25% each side, so a wide ornament can collide
 * with the neighbour, a pale tier can vanish against a light surface, and the
 * level badge can be swallowed by a corner flourish. All three are silent — the
 * page renders, nothing errors.
 *
 * So the screen deliberately shows the awkward combinations rather than a tidy
 * gallery:
 *
 *   · **three sizes**, because `sm` drops the level badge by design and that
 *     rule should be visible rather than remembered;
 *   · **three surfaces** — panel, recess, and a dark block — because a frame
 *     that reads well on white can disappear on the sidebar's recessed strip,
 *     and the light/dark pair is exactly where a hand-picked colour goes wrong;
 *   · **photo and initials**, because a frame sits on a photograph differently
 *     than on a flat colour tile;
 *   · **one, two and three digit levels**, because the badge is `min-w-5` with
 *     horizontal padding and only grows when the number does.
 *
 * It reads the ADMIN config, not `/profile/progression`: that endpoint returns
 * only the tier the viewer has actually reached, which is precisely the one
 * thing this screen must not depend on.
 */

/** A tier as `Avatar` wants it. The admin row carries two extra fields. */
function asPublic(row: ProgressionConfigAdmin["frames"][number]): FramePublic {
  return {
    code: row.code,
    label: row.label,
    min_level: row.min_level,
    tone: row.tone,
    ring: row.ring,
    image_url: row.image_url,
  };
}

/* Ảnh mẫu để thử khung trên ẢNH chứ không chỉ trên ô chữ cái. Dùng đúng một
   avatar có thật trên Cloudinary của dự án; không có thì rơi về chữ cái đầu, và
   đó cũng là một trường hợp cần nhìn. */
const SAMPLE_ID = "0f4a1f2c-1111-4444-8888-0f4a1f2c1111";

function Row({
  frame,
  level,
  src,
}: {
  frame: FramePublic | null;
  level: number;
  src: string | null;
}) {
  const shared = { id: SAMPLE_ID, name: "Đặng Ngọc Linh", email: "linh@example.com", src };
  return (
    <li className="grid items-center gap-4 border-t border-rule py-5 sm:grid-cols-[10rem_1fr]">
      <div>
        <p className="font-semibold">{frame ? frame.label : "Không khung"}</p>
        <p className="mt-0.5 font-data text-small tabular-nums text-ink-faint">
          {frame ? `${frame.code} · level ${frame.min_level}+` : "level 1–4"}
        </p>
        {frame && !frame.image_url && (
          <Tag tone="warn" className="mt-1.5">
            No art
          </Tag>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-8 gap-y-6">
        {/* Ba cỡ cạnh nhau: `sm` cố ý KHÔNG mang huy hiệu level. */}
        <div className="flex items-center gap-5">
          <Avatar {...shared} size="sm" frame={frame} level={level} />
          <Avatar {...shared} size="md" frame={frame} level={level} />
          <Avatar {...shared} size="lg" frame={frame} level={level} />
        </div>

        {/* Ba bề mặt. `recess` là nền của khối danh tính trong sidebar khi hover,
            và khối tối thay cho việc phải đổi theme để thấy bậc nhạt biến mất. */}
        <div className="flex items-center gap-3">
          <span className="rounded border border-rule bg-panel p-3">
            <Avatar {...shared} size="lg" frame={frame} level={level} />
          </span>
          <span className="rounded border border-rule bg-recess p-3">
            <Avatar {...shared} size="lg" frame={frame} level={level} />
          </span>
          <span className="rounded border border-rule bg-ink p-3">
            <Avatar {...shared} size="lg" frame={frame} level={level} />
          </span>
        </div>
      </div>
    </li>
  );
}

export default function FramePreviewPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [config, setConfig] = useState<ProgressionConfigAdmin | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(7);
  const [withPhoto, setWithPhoto] = useState(true);

  useEffect(() => {
    if (!token) return;
    apiFetch<ProgressionConfigAdmin>(API_ROUTES.adminProgression, { token })
      .then(setConfig)
      .catch(() => setError("Could not load the configuration. This page needs the admin role."));
  }, [token]);

  if (status !== "authenticated") {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-6 h-64" />
      </Page>
    );
  }

  /* Một ảnh thật để khung nằm lên ảnh; `null` thì Avatar rơi về chữ cái đầu. */
  const src = withPhoto
    ? "https://res.cloudinary.com/dwhaokd0c/image/upload/w_256,h_256,c_fill,g_face/sample.jpg"
    : null;

  return (
    <Page>
      <PageHeader
        eyebrow="Progression"
        title="Frame preview"
        description="Every tier through the real Avatar component, at three sizes and on three surfaces. Switch the theme in the header to check the other half."
        actions={
          <Link
            href="/admin/progression"
            className="text-small font-semibold text-ink-muted hover:text-ink"
          >
            Back to config
          </Link>
        }
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <Panel className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
        <span className="text-small font-semibold">Level badge</span>
        <div className="flex gap-2">
          {[7, 42, 99].map((value) => (
            <Button
              key={value}
              size="sm"
              variant={level === value ? "primary" : "secondary"}
              onClick={() => setLevel(value)}
            >
              {value}
            </Button>
          ))}
        </div>
        <span className="ml-auto text-small font-semibold">Face</span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={withPhoto ? "primary" : "secondary"}
            onClick={() => setWithPhoto(true)}
          >
            Photo
          </Button>
          <Button
            size="sm"
            variant={withPhoto ? "secondary" : "primary"}
            onClick={() => setWithPhoto(false)}
          >
            Initials
          </Button>
        </div>
      </Panel>

      {config === null && !error ? (
        <Skeleton className="h-96" />
      ) : (
        <Panel className="px-5 sm:px-6">
          <ul>
            {/* Baseline first: no frame at all is what levels 1–4 see, and every
                other row is only meaningful next to it. */}
            <Row frame={null} level={level} src={src} />
            {(config?.frames ?? [])
              .slice()
              .sort((a, b) => a.min_level - b.min_level)
              .map((row) => (
                <Row key={row.code} frame={asPublic(row)} level={level} src={src} />
              ))}
          </ul>
        </Panel>
      )}
    </Page>
  );
}
