"use client";

import {
  API_ROUTES,
  type HallPetBoard,
  type HallPetEntry,
  type HallUserBoard,
  type HallUserEntry,
} from "@toeic-pilot/shared";
import { Award, Crown, Medal } from "lucide-react";
import { useCallback, useEffect, type ReactNode, Children, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Creature, TIER_TONE } from "@/components/petland/petland-creature";
import { Alert, Page, PageHeader, Panel, SkeletonList, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Sảnh danh vọng: BXH level học viên + level thú cưng (SPEC-HALL-OF-FAME).
 *
 * Đọc CÔNG KHAI — trang không đòi phiên: khách xem được bảng, chỉ thiếu dòng
 * highlight và hạng của mình. Vì thế dùng `useSession` chứ không phải
 * `useRequireSession` (cái sau đá về /login).
 */

type Tab = "users" | "pets";

const LIMIT = 20;

/* Huy chương top 3: MỖI HẠNG MỘT HÌNH MỘT MÀU MỘT VIỀN — số "1,2,3" tô ba màu
   vẫn đọc ra là ba con số, còn ba hình khác nhau thì mắt phân biệt ngay cả khi
   không đọc số. Vàng dùng token warn (đã kiểm dark mode), bạc/xám dùng token
   ink có sẵn. */
const MEDAL = [
  { Icon: Crown, tone: "text-warn", border: "border-warn" },
  { Icon: Medal, tone: "text-ink", border: "border-ink" },
  { Icon: Award, tone: "text-ink-muted", border: "border-rule-strong" },
] as const;

function MyRank({ rank, total, noun }: { rank: number | null; total: number; noun: string }) {
  if (rank === null) return null;
  return (
    <p className="mb-4 rounded border border-action bg-action-tint px-4 py-2 text-small font-semibold text-action-ink">
      Hạng của bạn: {rank}/{total} {noun}
    </p>
  );
}

function LevelPill({ level }: { level: number }) {
  return (
    <span className="shrink-0 rounded bg-recess px-1.5 py-0.5 font-data text-small font-bold">
      Lv {level}
    </span>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const medal = rank <= 3 ? MEDAL[rank - 1] : undefined;
  return (
    <span
      className={cx(
        "grid h-8 w-8 shrink-0 place-items-center rounded-full border font-data text-body font-bold tabular-nums",
        medal ? medal.border : "border-rule",
        medal ? medal.tone : "text-ink-faint",
      )}
      aria-label={`Hạng ${rank}`}
    >
      {medal ? <medal.Icon size={16} strokeWidth={2} aria-hidden /> : rank}
    </span>
  );
}

function UserAvatar({ name, url, large }: { name: string; url?: string | null; large?: boolean }) {
  const size = large ? "h-16 w-16 text-title" : "h-10 w-10 text-body";
  /* Có ảnh thật thì hiện ảnh, không thì chữ cái đầu — cùng khuôn thẻ sidebar
     (ảnh vỡ thì alt rỗng + nền recess đỡ, không hiện icon vỡ). */
  if (url) {
    return (
      // `<img>` thường như `Avatar` ở `ui.tsx`: ảnh nằm trên host ngoài chưa khai
      // trong `images.remotePatterns`, và nhà cung cấp tối ưu + CDN sẵn rồi.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={url} alt="" className={`${size} shrink-0 rounded-full bg-recess object-cover`} />
    );
  }
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden
      className={`grid ${size} shrink-0 place-items-center rounded-full bg-recess font-bold text-ink`}
    >
      {initial}
    </span>
  );
}

function UserRow({ entry }: { entry: HallUserEntry }) {
  return (
    <li
      className={cx(
        "flex items-center gap-3 rounded border px-3 py-2",
        entry.is_me ? "border-action bg-action-tint" : "border-transparent hover:bg-recess",
      )}
    >
      <RankBadge rank={entry.rank} />
      <UserAvatar name={entry.display_name} url={entry.avatar_url} />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{entry.display_name}</span>
        <span className="block text-small tabular-nums text-ink-muted">{entry.xp_total} XP</span>
      </span>
      <LevelPill level={entry.level} />
    </li>
  );
}

function PetRow({ entry }: { entry: HallPetEntry }) {
  return (
    <li
      className={cx(
        "flex items-center gap-3 rounded border px-3 py-2",
        entry.is_me ? "border-action bg-action-tint" : "border-transparent hover:bg-recess",
      )}
    >
      <RankBadge rank={entry.rank} />
      <Creature tile={entry.tile} sheet={entry.sheet} tier={entry.tier} size={36} />
      <span className="min-w-0 flex-1">
        {/* Tên thú mang màu hạng, cùng `TIER_TONE` màn trứng dùng. */}
        <span className={cx("block truncate font-semibold", TIER_TONE[entry.tier] ?? "text-ink")}>
          {entry.nickname ?? entry.species}
        </span>
        <span className="block truncate text-small text-ink-muted">
          của {entry.display_name} · {entry.xp} XP
        </span>
      </span>
      <LevelPill level={entry.level} />
    </li>
  );
}

/* Ba thẻ podium: nhất ở giữa và cao hơn trên desktop, xếp dọc 1-2-3 trên
   mobile (order giữ nguyên thứ tự đọc). Không tách component podium riêng cho
   từng bảng — thẻ chỉ khác ruột, khung và huy chương giống nhau. */
function Podium({ children }: { children: ReactNode }) {
  const [first, second, third] = Children.toArray(children);
  return (
    <div className="mb-4 grid gap-2 sm:grid-cols-3">
      <div className="sm:order-1 sm:mt-4">{second}</div>
      <div className="order-first sm:order-2">{first}</div>
      <div className="sm:order-3 sm:mt-4">{third}</div>
    </div>
  );
}

function PodiumCard({
  rank,
  avatar,
  title,
  subtitle,
  footer,
  highlight,
}: {
  rank: number;
  avatar: React.ReactNode;
  title: React.ReactNode;
  subtitle: string;
  footer: React.ReactNode;
  highlight: boolean;
}) {
  const medal = rank <= 3 ? MEDAL[rank - 1] : undefined;
  return (
    <Panel
      className={cx(
        "flex flex-col items-center p-4 text-center",
        medal ? medal.border : "border-rule-strong",
        highlight && "bg-action-tint",
      )}
    >
      {medal ? (
        <medal.Icon size={26} strokeWidth={2} aria-label={`Hạng ${rank}`} className={medal.tone} />
      ) : (
        <span className="font-data text-title font-bold tabular-nums text-ink-muted">{rank}</span>
      )}
      <div className="mt-2">{avatar}</div>
      <p className="mt-2 w-full truncate font-semibold">{title}</p>
      <p className="w-full truncate text-small text-ink-muted">{subtitle}</p>
      <div className="mt-2">{footer}</div>
    </Panel>
  );
}

export default function HallOfFamePage() {
  const { token } = useSession();
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<HallUserBoard | null>(null);
  const [pets, setPets] = useState<HallPetBoard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((next: Tab, t?: string) => {
    const path = next === "users" ? API_ROUTES.hallUsers : API_ROUTES.hallPets;
    apiFetch<HallUserBoard | HallPetBoard>(`${path}?limit=${LIMIT}`, t ? { token: t } : {})
      .then((data) => {
        if (next === "users") setUsers(data as HallUserBoard);
        else setPets(data as HallPetBoard);
      })
      .catch(() => setError("Không tải được bảng xếp hạng."));
  }, []);

  // `token` đổi từ chưa-có thành có (phiên phân giải xong) thì đọc lại để có
  // highlight — cùng cái bẫy ba trạng thái mà `petland.tsx` ghi lại.
  useEffect(() => {
    load(tab, token ?? undefined);
  }, [tab, token, load]);

  const board = tab === "users" ? users : pets;
  const top = board?.entries.slice(0, 3) ?? [];

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/dashboard", label: "Bảng điều khiển" }]} />
      <PageHeader
        eyebrow="Sảnh danh vọng"
        title="Bảng xếp hạng"
        description="Level học viên và level thú cưng của mọi người — xem mình đang ở đâu."
      />
      {error && <Alert>{error}</Alert>}

      <div role="tablist" aria-label="Loại bảng xếp hạng" className="mb-4 flex gap-2">
        {(
          [
            ["users", "Học viên"],
            ["pets", "Thú cưng"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cx(
              "flex-1 rounded border px-4 py-1.5 text-small font-semibold transition-colors sm:flex-none",
              tab === key
                ? "border-action bg-action-tint text-action-ink"
                : "border-rule text-ink-muted hover:bg-recess",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {!board ? (
        <SkeletonList rows={6} />
      ) : (
        <>
          <MyRank
            rank={board.my_rank}
            total={board.total}
            noun={tab === "users" ? "người" : "thú cưng"}
          />
          {board.entries.length === 0 ? (
            <p className="rounded border border-rule p-4 text-small text-ink-muted">
              {tab === "pets"
                ? "Chưa ai mở trứng — bảng thú cưng đang trống."
                : "Chưa có ai trên bảng."}
            </p>
          ) : (
            <>
              <p className="mb-2 text-small text-ink-muted">
                {board.total} {tab === "users" ? "người" : "thú cưng"} trên bảng · top{" "}
                {Math.min(3, board.entries.length)} dẫn đầu
              </p>
              {top.length === 3 &&
                (tab === "users" ? (
                  <Podium>
                    {([0, 1, 2] as const).map((i) => {
                      const entry = (board as HallUserBoard).entries[i]!;
                      return (
                        <PodiumCard
                          key={`${entry.rank}-${entry.display_name}-${i}`}
                          rank={entry.rank}
                          avatar={
                            <UserAvatar name={entry.display_name} url={entry.avatar_url} large />
                          }
                          title={entry.display_name}
                          subtitle={`${entry.xp_total} XP`}
                          footer={<LevelPill level={entry.level} />}
                          highlight={entry.is_me}
                        />
                      );
                    })}
                  </Podium>
                ) : (
                  <Podium>
                    {([0, 1, 2] as const).map((i) => {
                      const entry = (board as HallPetBoard).entries[i]!;
                      return (
                        <PodiumCard
                          key={`${entry.rank}-${entry.species}-${i}`}
                          rank={entry.rank}
                          avatar={
                            <Creature
                              tile={entry.tile}
                              sheet={entry.sheet}
                              tier={entry.tier}
                              size={48}
                            />
                          }
                          title={entry.nickname ?? entry.species}
                          subtitle={`của ${entry.display_name}`}
                          footer={<LevelPill level={entry.level} />}
                          highlight={entry.is_me}
                        />
                      );
                    })}
                  </Podium>
                ))}
              <ol className="space-y-1">
                {tab === "users"
                  ? (board as HallUserBoard).entries
                      .slice(top.length === 3 ? 3 : 0)
                      .map((entry, index) => (
                        <UserRow
                          key={`${entry.rank}-${entry.display_name}-${index}`}
                          entry={entry}
                        />
                      ))
                  : (board as HallPetBoard).entries
                      .slice(top.length === 3 ? 3 : 0)
                      .map((entry, index) => (
                        <PetRow key={`${entry.rank}-${entry.species}-${index}`} entry={entry} />
                      ))}
              </ol>
            </>
          )}
        </>
      )}
    </Page>
  );
}
