"use client";

import {
  API_ROUTES,
  type LearningStats,
  type TokenResponse,
  type UserProfilePublic,
  type UserProfileUpdate,
} from "@toeic-pilot/shared";
import { CalendarDays, Flame, Headphones, Target } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  Alert,
  Avatar,
  Button,
  Field,
  FieldError,
  Input,
  Page,
  PageHeader,
  Panel,
  SectionHeader,
  Select,
  Skeleton,
  Spinner,
  Tag,
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
  { value: "en-US", label: "Mỹ" },
  { value: "en-GB", label: "Anh" },
  { value: "en-AU", label: "Úc" },
  { value: "en-CA", label: "Canada" },
];

/** `""` từ ô input là "để trống", và để trống nghĩa là xoá — tức `null`. */
function orNull(value: string): string | null {
  return value.trim() === "" ? null : value.trim();
}

function numberOrNull(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function StatTile({
  Icon,
  label,
  value,
  hint,
}: {
  Icon: typeof Flame;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2 text-ink-muted">
        <Icon size={16} strokeWidth={1.75} aria-hidden />
        <span className="text-small font-semibold">{label}</span>
      </div>
      <p className="mt-2 font-data text-title leading-none">{value}</p>
      {hint && <p className="mt-1.5 text-small text-ink-faint">{hint}</p>}
    </Panel>
  );
}

/**
 * Dải 14 ngày gần nhất.
 *
 * Cố ý KHÔNG hiện phần trăm hay điểm số, cùng lý do đã ghi cho dictation: con số
 * đó không giúp người học quyết định làm gì tiếp. Ô đậm hay nhạt trả lời đúng
 * câu hỏi họ đang hỏi — hôm qua mình có học không.
 */
function ActivityStrip({ days }: { days: LearningStats["recent"] }) {
  return (
    <div className="flex gap-1">
      {days.map((day) => {
        const total = day.reviews + day.dictation_items;
        const tone =
          total === 0
            ? "bg-recess"
            : total < 5
              ? "bg-action/40"
              : total < 20
                ? "bg-action/70"
                : "bg-action";
        return (
          <div
            key={day.date}
            title={`${day.date}: ${day.reviews} lượt ôn, ${day.dictation_items} câu nghe`}
            className={`h-8 flex-1 rounded ${tone}`}
          />
        );
      })}
    </div>
  );
}

export default function ProfilePage() {
  const session = useRequireSession();
  const { status, user, token, refresh } = session;

  const [stats, setStats] = useState<LearningStats | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const onSave = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token) return;
      setError(null);
      setSaved(false);
      setSaving(true);
      const form = new FormData(event.currentTarget);

      /*
       * Gửi TẤT CẢ các trường của biểu mẫu, kể cả trường rỗng — vì rỗng ở đây
       * thật sự có nghĩa là "xoá đi". Đó là lý do backend phân biệt khoá vắng
       * mặt với khoá mang null; nếu chỗ này lọc bỏ giá trị rỗng thì thao tác xoá
       * ngày thi sẽ không bao giờ tới được máy chủ.
       */
      const body: UserProfileUpdate = {
        display_name: orNull(String(form.get("display_name") ?? "")),
        timezone: String(form.get("timezone") ?? ""),
        locale: String(form.get("locale") ?? ""),
        target_score: numberOrNull(String(form.get("target_score") ?? "")),
        exam_date: orNull(String(form.get("exam_date") ?? "")),
        minutes_per_day: numberOrNull(String(form.get("minutes_per_day") ?? "")),
        daily_new_limit: numberOrNull(String(form.get("daily_new_limit") ?? "")),
        preferred_accent: orNull(String(form.get("preferred_accent") ?? "")),
      };

      try {
        await apiFetch<UserProfilePublic>(API_ROUTES.profile, {
          method: "PATCH",
          token,
          body: JSON.stringify(body),
        });
        // Hồ sơ nằm trong phiên, nên header phải đọc lại mới hiện tên mới.
        refresh();
        setSaved(true);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Không lưu được hồ sơ.");
      } finally {
        setSaving(false);
      }
    },
    [token, refresh],
  );

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
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </Page>
    );
  }

  const profile = user.profile;

  return (
    <Page>
      <PageHeader
        eyebrow="Tài khoản"
        title="Hồ sơ"
        description="Tên hiển thị, mục tiêu và cách bạn muốn học mỗi ngày."
      />

      <Panel className="flex items-center gap-4 p-5">
        <Avatar id={user.id} name={profile.display_name} email={user.email} size="lg" />
        <div className="min-w-0">
          <p className="truncate text-subtitle font-semibold">
            {profile.display_name ?? user.email}
          </p>
          <p className="truncate text-small text-ink-muted">{user.email}</p>
          <Tag tone="action" className="mt-1.5">
            {user.role}
          </Tag>
        </div>
      </Panel>

      <section className="mt-10">
        <SectionHeader title="Bạn đã học được gì" />
        {stats ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                Icon={Flame}
                label="Chuỗi ngày"
                value={`${stats.current_streak}`}
                hint={`Dài nhất: ${stats.longest_streak} ngày`}
              />
              <StatTile
                Icon={Target}
                label="Từ đã thuộc"
                value={`${stats.vocabulary_mastered}/${stats.vocabulary_total}`}
                hint={`${stats.vocabulary_due} từ đến hạn ôn`}
              />
              <StatTile
                Icon={Headphones}
                label="Câu nghe xong"
                value={`${stats.dictation_completed}`}
                hint={`${stats.dictation_attempts} lượt kiểm tra`}
              />
              <StatTile
                Icon={CalendarDays}
                label="Ngày đã học"
                value={`${stats.active_days}`}
                hint={`${stats.reviews_total} lượt ôn từ`}
              />
            </div>
            <div className="mt-4">
              <p className="mb-1.5 text-small text-ink-muted">14 ngày gần nhất</p>
              <ActivityStrip days={stats.recent} />
            </div>
          </>
        ) : (
          <Skeleton className="h-24 w-full" />
        )}
      </section>

      <section className="mt-10">
        <SectionHeader title="Thông tin và mục tiêu" />
        <Panel className="p-5">
          <form onSubmit={onSave} className="space-y-5" noValidate>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Tên hiển thị" hint="Để trống thì header hiện email của bạn.">
                <Input
                  name="display_name"
                  defaultValue={profile.display_name ?? ""}
                  maxLength={80}
                  placeholder="Đặng Ngọc Linh"
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

              <Field label="Điểm mục tiêu" hint="10–990, bước 5. Bỏ trống nếu chưa định.">
                <Input
                  name="target_score"
                  type="number"
                  min={10}
                  max={990}
                  step={5}
                  defaultValue={profile.target_score ?? ""}
                  placeholder="750"
                />
              </Field>

              <Field label="Ngày thi dự kiến">
                <Input name="exam_date" type="date" defaultValue={profile.exam_date ?? ""} />
              </Field>

              <Field label="Số phút học mỗi ngày" hint="5–480 phút.">
                <Input
                  name="minutes_per_day"
                  type="number"
                  min={5}
                  max={480}
                  defaultValue={profile.minutes_per_day ?? ""}
                  placeholder="30"
                />
              </Field>

              <Field
                label="Từ mới mỗi ngày"
                hint="Bỏ trống để dùng mặc định của hệ thống (hiện là 20)."
              >
                <Input
                  name="daily_new_limit"
                  type="number"
                  min={1}
                  max={200}
                  defaultValue={profile.daily_new_limit ?? ""}
                  placeholder="20"
                />
              </Field>
            </div>

            {error && <FieldError>{error}</FieldError>}
            {saved && !error && <Alert tone="ok">Đã lưu.</Alert>}

            <Button type="submit" disabled={saving}>
              {saving && <Spinner />}
              {saving ? "Đang lưu…" : "Lưu thay đổi"}
            </Button>
          </form>
        </Panel>
      </section>

      <section className="mt-10">
        <SectionHeader title="Mật khẩu" />
        <Panel className="p-5">
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
            {pwDone && !pwError && (
              <Alert tone="ok">
                Đã đổi mật khẩu. Các thiết bị khác đang đăng nhập sẽ bị đăng xuất.
              </Alert>
            )}

            <Button type="submit" disabled={pwSaving}>
              {pwSaving && <Spinner />}
              {pwSaving ? "Đang đổi…" : "Đổi mật khẩu"}
            </Button>
          </form>
        </Panel>
      </section>
    </Page>
  );
}
