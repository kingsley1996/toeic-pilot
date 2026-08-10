"use client";

import {
  API_ROUTES,
  type LearningStats,
  type TokenResponse,
  type UserProfilePublic,
  type UserProfileUpdate,
} from "@toeic-pilot/shared";
import {
  AudioLines,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  Clock,
  Flame,
  Globe,
  Headphones,
  KeyRound,
  Pencil,
  RotateCcw,
  Target,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { ContributionGraph } from "@/components/contribution-graph";
import { Modal } from "@/components/modal";
import { TargetScale, bandFor } from "@/components/target-scale";
import {
  Alert,
  Avatar,
  Button,
  Field,
  FieldError,
  IconButton,
  Input,
  Page,
  PageHeader,
  Panel,
  SectionHeader,
  Select,
  Skeleton,
  Spinner,
  Tag,
  ValueTile,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { setAccessToken } from "@/lib/auth-storage";
import { useRequireSession } from "@/lib/session";

/*
 * Danh sách múi giờ rút gọn, không phải toàn bộ IANA.
 *
 * Bản đầy đủ có hơn 600 mục và biến ô chọn thành một cuộn dài vô nghĩa với
 * người dùng Việt Nam. Máy chủ vẫn kiểm theo CSDL IANA thật, nên đây chỉ là
 * đường tắt của giao diện chứ không phải giới hạn của hệ thống — giá trị đang
 * lưu luôn được chèn vào danh sách kể cả khi nó không nằm trong đây.
 */
const COMMON_ZONES = [
  "Asia/Ho_Chi_Minh",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Sydney",
  "Europe/London",
  "Europe/Berlin",
  "America/New_York",
  "America/Los_Angeles",
  "UTC",
];

const ACCENTS = [
  { value: "en-US", label: "Giọng Mỹ" },
  { value: "en-GB", label: "Giọng Anh" },
  { value: "en-AU", label: "Giọng Úc" },
  { value: "en-CA", label: "Giọng Canada" },
];

/** Mặc định của hệ thống khi hồ sơ để trống — xem `NEW_CARDS_PER_DAY`. */
const DEFAULT_NEW_PER_DAY = 20;

/** `""` từ ô input là "để trống", và để trống nghĩa là xoá — tức `null`. */
function orNull(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text === "" ? null : text;
}

function numberOrNull(value: FormDataEntryValue | null): number | null {
  const text = String(value ?? "").trim();
  return text === "" ? null : Number(text);
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "long" }).format(new Date(iso));
}

/** Số ngày còn lại tới ngày thi, tính theo ngày lịch chứ không theo 24 giờ. */
function daysUntil(examDate: string, today: string): number {
  const toUtc = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number);
    return Date.UTC(y!, m! - 1, d!);
  };
  return Math.round((toUtc(examDate) - toUtc(today)) / 86_400_000);
}

/**
 * Ô thống kê.
 *
 * Con số dùng IBM Plex Mono tabular và cỡ lớn — đây là chỗ mắt phải dừng lại,
 * còn nhãn thì không. Không đổ bóng, không nhấc lên khi rê chuột (§6.3): hai
 * thứ đó là dấu hiệu rõ nhất của giao diện sinh tự động.
 */
function StatTile({
  Icon,
  label,
  value,
  unit,
  hint,
}: {
  Icon: typeof Flame;
  label: string;
  value: string;
  unit?: string;
  hint?: string;
}) {
  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2 text-ink-muted">
        <Icon size={15} strokeWidth={1.75} aria-hidden />
        <span className="text-label font-semibold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-2.5 font-data text-[1.75rem] font-semibold leading-none tabular-nums">
        {value}
        {unit && <span className="ml-1 text-body font-normal text-ink-faint">{unit}</span>}
      </p>
      {hint && <p className="mt-1.5 text-small text-ink-faint">{hint}</p>}
    </Panel>
  );
}

/** Nút "Sửa" của một mục. `Pencil` là icon bắt buộc cho khái niệm này (§8.4). */
function EditButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded border border-rule px-2.5 py-1 text-small font-semibold text-ink-muted transition-colors hover:border-rule-strong hover:bg-recess hover:text-ink"
    >
      <Pencil size={13} strokeWidth={2} aria-hidden />
      {label}
    </button>
  );
}

type EditTarget = "identity" | "goals" | "study";

export default function ProfilePage() {
  const session = useRequireSession();
  const { status, user, token, refresh } = session;

  const [stats, setStats] = useState<LearningStats | null>(null);
  const [editing, setEditing] = useState<EditTarget | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const [pwSaving, setPwSaving] = useState(false);
  const [pwDone, setPwDone] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    apiFetch<LearningStats>(API_ROUTES.profileStats, { token })
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => {
        /* Thống kê hỏng không được làm hỏng cả trang hồ sơ. */
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  /**
   * Lưu một phần hồ sơ.
   *
   * Mỗi hộp thoại chỉ gửi những trường của chính nó, và đó là điều `PATCH` được
   * thiết kế cho: khoá vắng mặt nghĩa là "để nguyên". Nhờ vậy sửa mục tiêu
   * không thể vô tình ghi đè tên hiển thị, kể cả khi hai tab cùng mở.
   */
  const save = useCallback(
    async (patch: UserProfileUpdate, note: string): Promise<boolean> => {
      if (!token) return false;
      setError(null);
      setSaving(true);
      try {
        await apiFetch<UserProfilePublic>(API_ROUTES.profile, {
          method: "PATCH",
          token,
          body: JSON.stringify(patch),
        });
        // Hồ sơ nằm trong phiên, nên header phải đọc lại mới hiện tên mới.
        refresh();
        setEditing(null);
        setSavedNote(note);
        return true;
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Không lưu được.");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [token, refresh],
  );

  const closeModal = useCallback(() => {
    setEditing(null);
    setError(null);
  }, []);

  const onChangePassword = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token) return;
      const form = event.currentTarget;
      const data = new FormData(form);
      setPwError(null);
      setPwDone(false);
      setPwSaving(true);

      try {
        const response = await apiFetch<TokenResponse>(API_ROUTES.changePassword, {
          method: "POST",
          token,
          body: JSON.stringify({
            current_password: String(data.get("current_password")),
            new_password: String(data.get("new_password")),
          }),
        });
        /*
         * Thay token NGAY. Máy chủ vừa vô hiệu hoá mọi token phát hành trước lúc
         * đổi — kể cả token vừa dùng để gửi chính yêu cầu này — nên không thay
         * thì thao tác kế tiếp trả 401 và người dùng bị đá ra trang đăng nhập
         * đúng lúc vừa đổi mật khẩu thành công.
         */
        setAccessToken(response.access_token);
        form.reset();
        setPwDone(true);
      } catch (err) {
        setPwError(err instanceof ApiError ? err.message : "Không đổi được mật khẩu.");
      } finally {
        setPwSaving(false);
      }
    },
    [token],
  );

  if (status !== "authenticated" || !user) {
    return (
      <Page>
        <Skeleton className="h-8 w-48" />
        <div className="mt-6 space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </Page>
    );
  }

  const profile = user.profile;
  const remaining = profile.exam_date && stats ? daysUntil(profile.exam_date, stats.today) : null;
  const hasGoals = Boolean(profile.target_score || profile.exam_date || profile.minutes_per_day);
  const accentLabel = ACCENTS.find((a) => a.value === profile.preferred_accent)?.label ?? null;

  return (
    <Page>
      <PageHeader
        eyebrow="Tài khoản"
        title="Hồ sơ"
        description="Mục tiêu của bạn, tiến độ đã đi được, và những gì hệ thống dùng để xếp lịch ôn."
      />

      {savedNote && (
        <div className="mb-6">
          <Alert tone="ok">{savedNote}</Alert>
        </div>
      )}

      {/*
       * Khối danh tính: nền `recess` chứ không `panel`.
       *
       * Nó là bậc nền CHÌM, không phải card nổi — đó là cách hệ này diễn đạt độ
       * sâu (§6.3), thay cho việc đổ bóng một cái card lên trên nền.
       */}
      <section className="rounded border border-rule bg-recess p-5 sm:p-6">
        <div className="flex flex-wrap items-start gap-5">
          <Avatar id={user.id} name={profile.display_name} email={user.email} size="lg" />

          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-3">
              <div className="min-w-0">
                <h2 className="truncate text-title leading-tight">
                  {profile.display_name ?? user.email}
                </h2>
                <p className="mt-0.5 truncate text-small text-ink-muted">{user.email}</p>
              </div>
              <IconButton
                icon={Pencil}
                aria-label="Sửa thông tin cá nhân"
                onClick={() => setEditing("identity")}
              />
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-small text-ink-faint">
              <Tag tone="action">{user.role}</Tag>
              {/* Múi giờ nằm cạnh danh tính chứ không nằm trong biểu mẫu: nó mô
                  tả người dùng này ở đâu, và nó là thứ quyết định chuỗi ngày. */}
              <span className="inline-flex items-center gap-1.5">
                <Globe size={13} strokeWidth={1.75} aria-hidden />
                {profile.timezone}
              </span>
              <span>Tham gia {formatDate(user.created_at)}</span>
            </div>
          </div>

          {stats && stats.current_streak > 0 && (
            <div className="flex items-center gap-2.5 rounded border border-rule-strong bg-panel px-4 py-3">
              <Flame size={20} strokeWidth={1.75} aria-hidden className="text-action" />
              <div>
                <p className="font-data text-title font-semibold leading-none tabular-nums">
                  {stats.current_streak}
                </p>
                <p className="mt-0.5 text-label uppercase text-ink-faint">ngày liên tiếp</p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* --- mục tiêu ---------------------------------------------------- */}
      <section className="mt-10">
        <SectionHeader
          title="Mục tiêu ôn thi"
          aside={
            hasGoals ? <EditButton label="Sửa" onClick={() => setEditing("goals")} /> : undefined
          }
        />

        {hasGoals ? (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <ValueTile
                Icon={Target}
                label="Điểm mục tiêu"
                value={profile.target_score}
                hint={profile.target_score ? bandFor(profile.target_score) : undefined}
                empty="Chưa đặt"
              />
              <ValueTile
                Icon={CalendarCheck}
                label="Ngày thi"
                numeric={false}
                value={profile.exam_date ? formatDate(profile.exam_date) : null}
                hint={
                  remaining === null
                    ? undefined
                    : remaining >= 0
                      ? `Còn ${remaining} ngày`
                      : "Đã qua"
                }
                empty="Chưa có lịch thi"
              />
              <ValueTile
                Icon={Clock}
                label="Học mỗi ngày"
                value={profile.minutes_per_day}
                unit="phút"
                empty="Chưa đặt"
              />
            </div>

            {profile.target_score && (
              <Panel className="mt-3 p-5 sm:p-6">
                <TargetScale target={profile.target_score} />
                {/*
                 * §10 nói thẳng: khi chưa quy đổi được thì NÓI RA, không hiện 0
                 * và không nội suy. Chưa có bài thi thử nào nên chưa có điểm ước
                 * tính, và vẽ đại một con số ở đây sẽ là con số sai duy nhất
                 * trên cả trang mà người học không có cách nào biết là sai.
                 */}
                <p className="mt-5 border-t border-rule pt-4 text-small text-ink-muted">
                  Chưa có điểm ước tính — phần thi thử chưa mở, nên thang trên chỉ hiện mốc bạn đặt.
                </p>
              </Panel>
            )}
          </>
        ) : (
          /*
           * Trạng thái rỗng NÓI RA bước tiếp theo (§9.6). "Chưa có dữ liệu"
           * không nói điều gì mà người đọc chưa tự suy ra được.
           */
          <Panel className="flex flex-wrap items-center gap-x-5 gap-y-3 p-5 sm:p-6">
            <Target size={22} strokeWidth={1.75} aria-hidden className="text-action" />
            <div className="min-w-[16rem] flex-1">
              <p className="font-semibold">Chưa có mục tiêu nào</p>
              <p className="mt-1 text-small text-ink-muted">
                Đặt điểm muốn đạt và ngày thi để thấy mình đang ở đâu trên thang năng lực — và để lộ
                trình sau này biết phải xếp lịch theo cái gì.
              </p>
            </div>
            <Button onClick={() => setEditing("goals")}>Đặt mục tiêu ngay</Button>
          </Panel>
        )}
      </section>

      {/* --- thống kê ----------------------------------------------------- */}
      <section className="mt-10">
        <SectionHeader title="Bạn đã học được gì" />
        {stats ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                Icon={BookOpen}
                label="Từ đã thuộc"
                value={`${stats.vocabulary_mastered}`}
                unit={`/ ${stats.vocabulary_total}`}
                hint={`${stats.vocabulary_due} từ đến hạn ôn`}
              />
              <StatTile
                Icon={Headphones}
                label="Câu nghe xong"
                value={`${stats.dictation_completed}`}
                hint={`${stats.dictation_attempts} lượt kiểm tra`}
              />
              <StatTile
                Icon={Flame}
                label="Chuỗi dài nhất"
                value={`${stats.longest_streak}`}
                unit="ngày"
                hint={`Hiện tại: ${stats.current_streak} ngày`}
              />
              <StatTile
                Icon={CalendarDays}
                label="Ngày đã học"
                value={`${stats.active_days}`}
                hint={`${stats.reviews_total} lượt ôn từ`}
              />
            </div>

            <Panel className="mt-3 p-5">
              <ContributionGraph
                calendar={stats.calendar}
                today={stats.today}
                windowDays={stats.window_days}
              />
            </Panel>
          </>
        ) : (
          <Skeleton className="h-40 w-full" />
        )}
      </section>

      {/* --- cách học ----------------------------------------------------- */}
      <section className="mt-10">
        <SectionHeader
          title="Cách học"
          aside={<EditButton label="Sửa" onClick={() => setEditing("study")} />}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <ValueTile
            Icon={RotateCcw}
            label="Từ mới mỗi ngày"
            value={profile.daily_new_limit ?? DEFAULT_NEW_PER_DAY}
            unit="từ"
            hint={profile.daily_new_limit ? undefined : "Đang dùng mặc định của hệ thống"}
            empty="Chưa đặt"
          />
          <ValueTile
            Icon={AudioLines}
            label="Giọng đọc"
            numeric={false}
            value={accentLabel ?? "Cả bốn giọng"}
            hint={accentLabel ? undefined : "Không ưu tiên giọng nào"}
            empty="Chưa đặt"
          />
        </div>
      </section>

      {/* --- mật khẩu ----------------------------------------------------- */}
      <section className="mt-10">
        <SectionHeader title="Mật khẩu" />
        <Panel className="p-5 sm:p-6">
          <div className="mb-4 flex items-start gap-2.5 text-small text-ink-muted">
            <KeyRound size={16} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
            <p>
              Đổi mật khẩu sẽ đăng xuất mọi thiết bị khác đang đăng nhập. Thiết bị này thì không.
            </p>
          </div>
          {/* Biểu mẫu ở đây là ĐÚNG chỗ, khác với các mục trên: đổi mật khẩu là
              một hành động, không phải một giá trị để xem lại. */}
          <form onSubmit={onChangePassword} className="max-w-md space-y-4" noValidate>
            <Field label="Mật khẩu hiện tại">
              <Input
                name="current_password"
                type="password"
                required
                autoComplete="current-password"
              />
            </Field>
            <Field
              label="Mật khẩu mới"
              hint="Ít nhất 8 ký tự. Mật khẩu có dấu tiếng Việt tốn nhiều chỗ hơn, tối đa khoảng 24 ký tự."
            >
              <Input
                name="new_password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
              />
            </Field>

            {pwError && <FieldError>{pwError}</FieldError>}
            {pwDone && !pwError && <Alert tone="ok">Đã đổi mật khẩu.</Alert>}

            <Button type="submit" disabled={pwSaving}>
              {pwSaving && <Spinner />}
              {pwSaving ? "Đang đổi…" : "Đổi mật khẩu"}
            </Button>
          </form>
        </Panel>
      </section>

      {/* --- hộp thoại ---------------------------------------------------- */}
      {/*
       * Dựng có điều kiện chứ không giữ sẵn rồi bật `open`: các ô nhập dùng
       * `defaultValue` (không kiểm soát), nên chỉ khi component được gắn lại
       * chúng mới nhận giá trị vừa lưu. Giữ sẵn thì mở lần thứ hai sẽ hiện lại
       * số cũ.
       */}
      {editing === "identity" && (
        <Modal open onClose={closeModal} title="Thông tin cá nhân">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void save(
                {
                  display_name: orNull(data.get("display_name")),
                  timezone: String(data.get("timezone")),
                  locale: String(data.get("locale")),
                },
                "Đã cập nhật thông tin cá nhân.",
              );
            }}
            className="space-y-4"
            noValidate
          >
            <Field label="Tên hiển thị" hint="Để trống thì hệ thống hiện email của bạn.">
              <Input
                name="display_name"
                defaultValue={profile.display_name ?? ""}
                maxLength={80}
                placeholder="Đặng Ngọc Linh"
                autoFocus
              />
            </Field>
            <Field
              label="Múi giờ"
              hint="Quyết định một ngày học của bạn kết thúc lúc nào, nên nó quyết định cả chuỗi ngày."
            >
              <Select name="timezone" defaultValue={profile.timezone}>
                {(COMMON_ZONES.includes(profile.timezone)
                  ? COMMON_ZONES
                  : [profile.timezone, ...COMMON_ZONES]
                ).map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Ngôn ngữ giao diện">
              <Select name="locale" defaultValue={profile.locale}>
                <option value="vi">Tiếng Việt</option>
                <option value="en">English</option>
              </Select>
            </Field>

            {error && <FieldError>{error}</FieldError>}

            <div className="flex justify-end gap-2 border-t border-rule pt-4">
              <Button type="button" variant="quiet" onClick={closeModal}>
                Huỷ
              </Button>
              <Button type="submit" disabled={saving}>
                {saving && <Spinner />}
                {saving ? "Đang lưu…" : "Lưu"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editing === "goals" && (
        <Modal
          open
          onClose={closeModal}
          title="Mục tiêu ôn thi"
          description="Bỏ trống một ô để xoá mốc đó."
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void save(
                {
                  target_score: numberOrNull(data.get("target_score")),
                  exam_date: orNull(data.get("exam_date")),
                  minutes_per_day: numberOrNull(data.get("minutes_per_day")),
                },
                "Đã cập nhật mục tiêu.",
              );
            }}
            className="space-y-4"
            noValidate
          >
            <Field label="Điểm mục tiêu" hint="10–990, đi theo bước 5.">
              <Input
                name="target_score"
                type="number"
                min={10}
                max={990}
                step={5}
                defaultValue={profile.target_score ?? ""}
                placeholder="750"
                autoFocus
              />
            </Field>
            <Field label="Ngày thi dự kiến">
              <Input name="exam_date" type="date" defaultValue={profile.exam_date ?? ""} />
            </Field>
            <Field label="Số phút học mỗi ngày" hint="Từ 5 đến 480 phút.">
              <Input
                name="minutes_per_day"
                type="number"
                min={5}
                max={480}
                defaultValue={profile.minutes_per_day ?? ""}
                placeholder="30"
              />
            </Field>

            {error && <FieldError>{error}</FieldError>}

            <div className="flex justify-end gap-2 border-t border-rule pt-4">
              <Button type="button" variant="quiet" onClick={closeModal}>
                Huỷ
              </Button>
              <Button type="submit" disabled={saving}>
                {saving && <Spinner />}
                {saving ? "Đang lưu…" : "Lưu"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editing === "study" && (
        <Modal open onClose={closeModal} title="Cách học">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              void save(
                {
                  daily_new_limit: numberOrNull(data.get("daily_new_limit")),
                  preferred_accent: orNull(data.get("preferred_accent")),
                },
                "Đã cập nhật cách học.",
              );
            }}
            className="space-y-4"
            noValidate
          >
            <Field
              label="Từ mới mỗi ngày"
              hint={`Bỏ trống để dùng mặc định của hệ thống (${DEFAULT_NEW_PER_DAY}).`}
            >
              <Input
                name="daily_new_limit"
                type="number"
                min={1}
                max={200}
                defaultValue={profile.daily_new_limit ?? ""}
                placeholder={`${DEFAULT_NEW_PER_DAY}`}
                autoFocus
              />
            </Field>
            <Field label="Giọng đọc ưu tiên" hint="Để trống để nghe đủ cả bốn giọng.">
              <Select name="preferred_accent" defaultValue={profile.preferred_accent ?? ""}>
                <option value="">Không ưu tiên</option>
                {ACCENTS.map((accent) => (
                  <option key={accent.value} value={accent.value}>
                    {accent.label}
                  </option>
                ))}
              </Select>
            </Field>

            {error && <FieldError>{error}</FieldError>}

            <div className="flex justify-end gap-2 border-t border-rule pt-4">
              <Button type="button" variant="quiet" onClick={closeModal}>
                Huỷ
              </Button>
              <Button type="submit" disabled={saving}>
                {saving && <Spinner />}
                {saving ? "Đang lưu…" : "Lưu"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </Page>
  );
}
