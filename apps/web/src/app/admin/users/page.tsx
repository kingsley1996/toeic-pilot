"use client";

import {
  API_ROUTES,
  type AdminUserPage,
  type AdminUserPublic,
  type AdminUserStats,
  type UserActivity,
} from "@toeic-pilot/shared";
import { Activity, Gem, ShieldCheck, Trash2, UserPlus, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Modal } from "@/components/modal";
import {
  Alert,
  Button,
  EmptyState,
  Input,
  Page,
  PageHeader,
  Pager,
  Panel,
  Select,
  SkeletonList,
  Tag,
  ValueTile,
  cx,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Thành viên — nhịp sống của ứng dụng.
 *
 * Một màn cho hết vòng đời: ai vừa đăng ký, đang hoạt động ra sao, tăng
 * trưởng thế nào, và các thao tác vận hành (đổi quyền, cấp ruby, xoá). Cấp
 * ruby ở đây là hàng sổ cái `admin_grant` phía server — màn này không có ô
 * nào để gõ thẳng số dư, và đó là cố ý.
 */

const ROLES = ["learner", "editor", "admin"] as const;
const LIMIT = 25;

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "vừa xong";
  if (s < 3600) return `${Math.floor(s / 60)} phút trước`;
  if (s < 86400) return `${Math.floor(s / 3600)} giờ trước`;
  return `${Math.floor(s / 86400)} ngày trước`;
}

export default function AdminUsersPage() {
  const { token, user: me } = useRequireSession({ canEdit: true });
  const [stats, setStats] = useState<AdminUserStats | null>(null);
  const [page, setPage] = useState<AdminUserPage | null>(null);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const [creating, setCreating] = useState(false);
  const [grant, setGrant] = useState<AdminUserPublic | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<AdminUserPublic | null>(null);
  const [activityOf, setActivityOf] = useState<AdminUserPublic | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    apiFetch<AdminUserPage>(
      API_ROUTES.adminUsers +
        `?limit=${LIMIT}&offset=${offset}` +
        (q ? `&q=${encodeURIComponent(q)}` : ""),
      { token },
    )
      .then(setPage)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không tải được danh sách."),
      );
    apiFetch<AdminUserStats>(API_ROUTES.adminUserStats, { token })
      .then(setStats)
      .catch(() => {});
  }, [token, offset, q]);

  useEffect(() => {
    load();
  }, [load]);

  // Gõ mượt chứ không bắn request theo từng phím: ô tìm kiếm nạp lại danh
  // sách sau 300ms im lặng — setState nằm trong setTimeout chứ không thân
  // effect, đúng khe `react-hooks/set-state-in-effect` cho phép.
  useEffect(() => {
    const t = window.setTimeout(() => {
      setQ(qInput);
      setOffset(0);
    }, 300);
    return () => window.clearTimeout(t);
  }, [qInput]);

  function act(user: AdminUserPublic, body: Record<string, unknown>, path: string) {
    if (!token) return;
    setError(null);
    apiFetch<AdminUserPublic>(path, { method: "POST", token, body: JSON.stringify(body) })
      .then(() => load())
      .catch((err) => setError(err instanceof ApiError ? err.message : "Thao tác thất bại."));
  }

  const rows = page?.items ?? [];
  const maxDay = Math.max(1, ...(stats?.growth.map((g) => g.count) ?? [1]));

  return (
    <Page>
      <PageHeader
        title="Thành viên"
        description="Người dùng mới, nhịp hoạt động, và các thao tác vận hành trên từng tài khoản."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {stats && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <ValueTile Icon={Users} label="Tổng thành viên" value={stats.total} empty="—" />
            <ValueTile Icon={UserPlus} label="Mới · 7 ngày" value={stats.new_7d} empty="—" />
            <ValueTile
              Icon={Activity}
              label="Hoạt động · 7 ngày"
              value={stats.active_7d}
              empty="—"
            />
            <ValueTile Icon={ShieldCheck} label="Mới · 30 ngày" value={stats.new_30d} empty="—" />
          </div>
          <Panel className="mt-3 p-4">
            <p className="text-label font-semibold uppercase text-ink-faint">Tăng trưởng 30 ngày</p>
            <div
              className="mt-3 flex h-16 items-end gap-px"
              role="img"
              aria-label={`Biểu đồ đăng ký theo ngày, cao nhất ${maxDay}`}
            >
              {stats.growth.map((g) => (
                <div
                  key={g.day}
                  title={`${g.day}: ${g.count}`}
                  className={cx(
                    "min-w-0 flex-1 rounded-sm",
                    g.count > 0 ? "bg-action" : "bg-recess",
                  )}
                  style={{ height: `${Math.max(4, (g.count / maxDay) * 100)}%` }}
                />
              ))}
            </div>
          </Panel>
        </>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Input
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="Tìm email…"
          aria-label="Tìm theo email"
          className="w-64"
        />
        <Button variant="secondary" onClick={() => setCreating(true)}>
          <UserPlus size={14} strokeWidth={2} className="mr-1.5" aria-hidden />
          Thêm thành viên
        </Button>
      </div>

      <div className="mt-4 overflow-x-auto rounded border border-rule">
        <table className="w-full text-small">
          <thead>
            <tr className="border-b border-rule bg-recess text-left text-label uppercase text-ink-muted">
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Quyền</th>
              <th className="px-3 py-2 text-right">Ruby</th>
              <th className="px-3 py-2 text-right">Đã làm đề</th>
              <th className="px-3 py-2">Hoạt động cuối</th>
              <th className="px-3 py-2">Đăng ký</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {rows.map((u) => (
              <tr key={u.id} className="hover:bg-recess">
                <td className="px-3 py-2 font-medium">{u.email}</td>
                <td className="px-3 py-2">
                  <Select
                    aria-label={`Quyền của ${u.email}`}
                    value={u.role}
                    disabled={u.id === me?.id}
                    onChange={(e) =>
                      token &&
                      void apiFetch(API_ROUTES.adminUser(u.id), {
                        method: "PATCH",
                        token,
                        body: JSON.stringify({ role: e.target.value }),
                      })
                        .then(load)
                        // Select đã vẽ giá trị mới; server từ chối thì nạp lại
                        // để nó về giá trị thật thay vì nói dối bằng UI cũ.
                        .catch(() => {
                          setError("Không đổi được quyền.");
                          load();
                        })
                    }
                    className="w-auto py-1 text-small"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>
                </td>
                <td className="px-3 py-2 text-right font-data tabular-nums">{u.ruby_balance}</td>
                <td className="px-3 py-2 text-right font-data tabular-nums">{u.attempt_count}</td>
                <td className="px-3 py-2 text-ink-muted">{timeAgo(u.last_activity)}</td>
                <td className="px-3 py-2 text-ink-muted">
                  {new Date(u.created_at).toLocaleDateString("vi-VN")}
                </td>
                <td className="px-3 py-2">
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="quiet"
                      size="sm"
                      aria-label={`Hoạt động của ${u.email}`}
                      onClick={() => setActivityOf(u)}
                    >
                      <Activity size={14} strokeWidth={2} aria-hidden />
                    </Button>
                    <Button
                      variant="quiet"
                      size="sm"
                      aria-label={`Cấp ruby cho ${u.email}`}
                      onClick={() => setGrant(u)}
                    >
                      <Gem size={14} strokeWidth={2} aria-hidden />
                    </Button>
                    <Button
                      variant="quiet"
                      size="sm"
                      aria-label={`Xoá ${u.email}`}
                      disabled={u.id === me?.id}
                      onClick={() => setConfirmDelete(u)}
                    >
                      <Trash2 size={14} strokeWidth={2} className="text-alert" aria-hidden />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!page && (
          <div className="p-4">
            <SkeletonList rows={4} />
          </div>
        )}
        {page && rows.length === 0 && (
          <EmptyState
            icon={Users}
            title="Không có ai khớp"
            description="Thử tìm bằng chuỗi khác."
          />
        )}
      </div>
      {page && (
        <div className="mt-4">
          <Pager total={page.total} limit={LIMIT} offset={offset} onOffset={setOffset} />
        </div>
      )}

      {creating && (
        <CreateModal
          onClose={() => setCreating(false)}
          onDone={() => {
            setCreating(false);
            load();
          }}
        />
      )}

      <Modal
        open={grant !== null}
        onClose={() => setGrant(null)}
        title={`Cấp ruby cho ${grant?.email ?? ""}`}
        description="Một hàng sổ cái `admin_grant` — số dư là tổng của sổ, không phải một ô để sửa."
      >
        <GrantForm
          balance={grant?.ruby_balance ?? 0}
          onGrant={(amount) => {
            if (grant) act(grant, { amount }, API_ROUTES.adminUserRuby(grant.id));
            setGrant(null);
          }}
        />
      </Modal>

      <Modal
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title={`Xoá tài khoản ${confirmDelete?.email ?? ""}?`}
        description="Mọi bài làm, tiến độ và sổ ruby của người này bị xoá theo. Không hoàn lại."
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmDelete(null)}>
            Huỷ
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              if (confirmDelete && token) {
                apiFetch(API_ROUTES.adminUser(confirmDelete.id), { method: "DELETE", token })
                  .then(load)
                  .catch(() => setError("Không xoá được."));
              }
              setConfirmDelete(null);
            }}
          >
            Xoá
          </Button>
        </div>
      </Modal>

      {activityOf && <ActivityModal user={activityOf} onClose={() => setActivityOf(null)} />}
    </Page>
  );
}

function CreateModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { token } = useRequireSession({ canEdit: true });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("learner");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    apiFetch(API_ROUTES.adminUsers, {
      method: "POST",
      token,
      body: JSON.stringify({ email, password, role }),
    })
      .then(onDone)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Không tạo được tài khoản.");
        setBusy(false);
      });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Thêm thành viên"
      description="Tài khoản mới đã có mật khẩu — người được tạo có thể đổi ở trang hồ sơ."
    >
      <div className="space-y-3">
        <Input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email@example.com"
          type="email"
          aria-label="Email"
        />
        <Input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mật khẩu (≥ 8 ký tự)"
          type="password"
          aria-label="Mật khẩu"
        />
        <Select
          value={role}
          onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
          aria-label="Quyền"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
        {error && <p className="text-small text-alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Huỷ
          </Button>
          <Button disabled={busy || !email || password.length < 8} onClick={submit}>
            {busy ? "Đang tạo…" : "Tạo"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function GrantForm({ balance, onGrant }: { balance: number; onGrant: (amount: number) => void }) {
  const [amount, setAmount] = useState("500");
  return (
    <div className="space-y-3">
      <p className="text-small text-ink-muted">
        Số dư hiện tại: <span className="font-data tabular-nums text-ink">{balance}</span>
      </p>
      <Input
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        type="number"
        min={1}
        max={10000}
        aria-label="Số ruby"
      />
      <div className="flex justify-end">
        <Button
          onClick={() => {
            const n = Number(amount);
            if (n > 0) onGrant(n);
          }}
        >
          Cấp
        </Button>
      </div>
    </div>
  );
}

function ActivityModal({ user, onClose }: { user: AdminUserPublic; onClose: () => void }) {
  const { token } = useRequireSession({ canEdit: true });
  const [events, setEvents] = useState<UserActivity[] | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<UserActivity[]>(API_ROUTES.adminUserActivity(user.id), { token })
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [token, user.id]);

  return (
    <Modal
      open
      onClose={onClose}
      title={`Hoạt động của ${user.email}`}
      description="Ba mươi thao tác gần nhất, mới trước."
    >
      {!events && <SkeletonList rows={3} />}
      {events && events.length === 0 && (
        <p className="text-small text-ink-muted">Người này chưa làm gì cả.</p>
      )}
      <ul className="space-y-2">
        {events?.map((e, i) => (
          <li key={i} className="flex items-center gap-3 text-small">
            <Tag>{e.kind}</Tag>
            <span className="min-w-0 flex-1 truncate">{e.label}</span>
            <span className="shrink-0 text-ink-faint">{timeAgo(e.at)}</span>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
