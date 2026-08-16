"use client";

import {
  API_ROUTES,
  type CollectionAdmin,
  type TestAdmin,
  type TestAdminPage,
} from "@toeic-pilot/shared";
import { ClipboardList, FileText, FolderTree, Send, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  EmptyState,
  Field,
  FieldError,
  Input,
  Page,
  PageHeader,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Tag,
  cx,
} from "@/components/ui";
import { Modal } from "@/components/modal";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/*
 * Nội dung luyện thi là một CÂY ba tầng — bộ đề -> đề -> câu hỏi — và mỗi tầng
 * có trạng thái xuất bản riêng. Trang này là hai tầng trên.
 *
 * Xếp đề *bên trong* bộ đề chứ không thành một danh sách phẳng có thêm một cột
 * "bộ đề": danh sách phẳng giấu mất chuyện một bộ đề đang rỗng, mà bộ đề rỗng
 * lại đúng là thứ không xuất bản được và cần nhìn thấy.
 */

const NO_COLLECTION = "__none__";

export default function AdminTestsPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [tests, setTests] = useState<TestAdmin[] | null>(null);
  const [collections, setCollections] = useState<CollectionAdmin[] | null>(null);

  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("full");
  const [minutes, setMinutes] = useState("120");
  const [collectionSlug, setCollectionSlug] = useState(NO_COLLECTION);

  const [collectionForm, setCollectionForm] = useState({ slug: "", title: "", year: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 0 = không bị cắt; khác 0 là tổng số thật.
  const [truncated, setTruncated] = useState(0);

  const refresh = useCallback((t: string) => {
    // Màn này render CÂY — bộ đề chứa đề — nên không phân trang danh sách phẳng
    // được: trang 2 sẽ hiện một bộ với 3 trong 8 đề của nó và không có gì nói
    // rằng còn thiếu. Lấy tối đa một trang, và nếu vẫn không đủ thì NÓI RA thay
    // vì lặng lẽ dựng một cái cây khuyết.
    apiFetch<TestAdminPage>(`${API_ROUTES.adminTests}?limit=200`, { token: t })
      .then((page) => {
        setTests(page.items);
        setTruncated(page.total > page.items.length ? page.total : 0);
      })
      .catch(() => setError("Không tải được danh sách đề."));
    apiFetch<CollectionAdmin[]>(API_ROUTES.adminTestCollections, { token: t })
      .then(setCollections)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  async function run(work: () => Promise<unknown>, after?: () => void): Promise<string | null> {
    if (!token || busy) return "Đang bận.";
    setBusy(true);
    setError(null);
    try {
      // `await work()` là câu lệnh riêng — xem chú thích ở trang chi tiết đề:
      // nhét nó vào đối số của `done?.(...)` thì công việc không bao giờ chạy.
      await work();
      after?.();
      refresh(token);
      return null;
    } catch (problem) {
      const message = problem instanceof ApiError ? problem.message : "Có lỗi xảy ra.";
      setError(message);
      return message;
    } finally {
      setBusy(false);
    }
  }

  const createCollection = () =>
    run(
      () =>
        apiFetch(API_ROUTES.adminTestCollections, {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({
            slug: collectionForm.slug.trim(),
            title: collectionForm.title.trim(),
            year: collectionForm.year ? Number(collectionForm.year) : null,
          }),
        }),
      () => setCollectionForm({ slug: "", title: "", year: "" }),
    );

  const createTest = () =>
    run(
      () =>
        apiFetch(API_ROUTES.adminTests, {
          method: "POST",
          token: token ?? undefined,
          body: JSON.stringify({
            slug: slug.trim(),
            title: title.trim(),
            kind,
            time_limit_seconds: minutes ? Number(minutes) * 60 : null,
            collection_slug: collectionSlug === NO_COLLECTION ? null : collectionSlug,
          }),
        }),
      () => {
        setSlug("");
        setTitle("");
      },
    );

  const archiveCollection = (target: string, archived: boolean) =>
    run(() =>
      apiFetch(API_ROUTES.adminCollectionArchive(target), {
        method: "POST",
        token: token ?? undefined,
        body: JSON.stringify({ archived }),
      }),
    );

  const deleteCollection = (target: string, force = false) =>
    run(() =>
      apiFetch(API_ROUTES.adminCollection(target) + (force ? "?force=true" : ""), {
        method: "DELETE",
        token: token ?? undefined,
      }),
    );

  const publishCollection = (target: string) =>
    run(() =>
      apiFetch(API_ROUTES.adminTestCollectionPublish(target), {
        method: "POST",
        token: token ?? undefined,
      }),
    );

  if (status === "loading") {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  const loose = (tests ?? []).filter((test) => test.collection_slug === null);

  return (
    <Page>
      <PageHeader
        eyebrow="Nội dung"
        title="Đề thi"
        description="Bộ đề chứa đề, đề chứa câu hỏi. Mỗi tầng xuất bản riêng, và tầng trên bị chặn khi tầng dưới còn nháp."
      />

      {truncated > 0 && (
        <Alert tone="warn">
          Đang hiện 200 đề đầu trong tổng số {truncated}. Màn này dựng theo cây bộ đề nên chưa lật
          trang được — cần lọc theo bộ đề trước khi danh sách vượt quá đây.
        </Alert>
      )}

      {error && (
        <div className="mb-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      <SectionHeader title="Tạo bộ đề" />
      <Panel className="p-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Slug">
            <Input
              value={collectionForm.slug}
              onChange={(e) => setCollectionForm({ ...collectionForm, slug: e.target.value })}
              placeholder="toeic-2026"
            />
          </Field>
          <Field label="Tên bộ đề">
            <Input
              value={collectionForm.title}
              onChange={(e) => setCollectionForm({ ...collectionForm, title: e.target.value })}
              placeholder="Bộ đề TOEIC 2026"
            />
          </Field>
          <Field label="Năm" hint="Để trống nếu không gắn với năm nào.">
            <Input
              value={collectionForm.year}
              onChange={(e) =>
                setCollectionForm({ ...collectionForm, year: e.target.value.replace(/\D/g, "") })
              }
              inputMode="numeric"
            />
          </Field>
        </div>
        <div className="mt-4">
          <Button
            variant="secondary"
            onClick={() => void createCollection()}
            disabled={busy || !collectionForm.slug.trim() || !collectionForm.title.trim()}
          >
            Tạo bộ đề
          </Button>
        </div>
      </Panel>

      <div className="mt-8">
        <SectionHeader title="Tạo đề" />
      </div>
      <Panel className="p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Slug" hint="Dùng trong đường dẫn. Không đổi được sau khi tạo.">
            <Input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="toeic-2026-test-1"
            />
          </Field>
          <Field label="Tên đề">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="TOEIC 2026 — Test 1"
            />
          </Field>
          {/* Chọn bộ đề ngay lúc tạo. Vẫn đổi được sau ở trang chi tiết, nhưng
              hỏi ở đây thì đề không rơi vào trạng thái mồ côi ngay từ đầu. */}
          <Field label="Thuộc bộ đề">
            <Select value={collectionSlug} onChange={(e) => setCollectionSlug(e.target.value)}>
              <option value={NO_COLLECTION}>— chưa thuộc bộ nào —</option>
              {(collections ?? []).map((collection) => (
                <option key={collection.id} value={collection.slug}>
                  {collection.title}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Loại" hint="full = 200 câu, mini = đề rút gọn.">
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="full">Đề đầy đủ</option>
              <option value="mini">Đề rút gọn</option>
            </Select>
          </Field>
          <Field label="Giới hạn giờ (phút)" hint="Để trống nghĩa là không giới hạn.">
            <Input
              value={minutes}
              onChange={(e) => setMinutes(e.target.value.replace(/\D/g, ""))}
              inputMode="numeric"
            />
          </Field>
        </div>
        <div className="mt-4">
          <Button
            onClick={() => void createTest()}
            disabled={busy || !slug.trim() || !title.trim()}
          >
            Tạo đề
          </Button>
        </div>
      </Panel>

      <section className="mt-10">
        <SectionHeader title="Cây nội dung" />
        {tests === null || collections === null ? (
          <SkeletonList rows={3} />
        ) : collections.length === 0 && tests.length === 0 ? (
          <EmptyState
            icon={FolderTree}
            title="Chưa có gì cả"
            description="Tạo một bộ đề, rồi tạo đề bên trong nó."
          />
        ) : (
          <div className="space-y-4">
            {collections.map((collection) => (
              <CollectionBlock
                key={collection.id}
                collection={collection}
                tests={tests.filter((test) => test.collection_slug === collection.slug)}
                canPublish={canPublish}
                busy={busy}
                onPublish={() => void publishCollection(collection.slug)}
                onArchive={(archived) => void archiveCollection(collection.slug, archived)}
                onDelete={(force) => deleteCollection(collection.slug, force)}
              />
            ))}

            {loose.length > 0 && (
              <div>
                {/* Đề chưa thuộc bộ nào KHÔNG bị giấu đi: người học không thấy
                    chúng ở đâu cả, nên nếu màn quản trị cũng không hiện thì
                    chúng biến mất khỏi tầm mắt mà vẫn nằm trong database. */}
                <p className="mb-1.5 text-label font-semibold uppercase text-ink-muted">
                  Chưa thuộc bộ nào — người học không nhìn thấy
                </p>
                <div className="space-y-2">
                  {loose.map((test) => (
                    <TestRow key={test.id} test={test} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </Page>
  );
}

function CollectionBlock({
  collection,
  tests,
  canPublish,
  busy,
  onPublish,
  onArchive,
  onDelete,
}: {
  collection: CollectionAdmin;
  tests: TestAdmin[];
  canPublish: boolean;
  busy: boolean;
  onPublish: () => void;
  onArchive: (archived: boolean) => void;
  onDelete: (force?: boolean) => Promise<string | null>;
}) {
  const [confirming, setConfirming] = useState(false);
  // Từ chối xoá phải in TRONG hộp thoại: băng lỗi chung nằm sau lớp phủ
  // `<dialog>`, nên một cú 409 hiện ở đầu trang là vô hình.
  const [refusal, setRefusal] = useState<string | null>(null);

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <FolderTree size={16} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
            <p className="font-semibold">{collection.title}</p>
            <PublishTag status={collection.status} />
            {collection.year !== null && <Tag>{collection.year}</Tag>}
            <span className="font-data text-small text-ink-faint">{collection.slug}</span>
          </div>
          <p className="mt-1 text-small text-ink-muted">
            <span className="font-data tabular-nums">{collection.published_test_count}</span>/
            <span className="font-data tabular-nums">{collection.test_count}</span> đề đã xuất bản
          </p>
        </div>
        {canPublish && collection.status !== "published" && (
          <Button
            size="sm"
            variant="secondary"
            onClick={onPublish}
            disabled={busy || collection.published_test_count === 0}
            title={
              collection.published_test_count === 0
                ? "Chưa có đề nào đã xuất bản — bộ đề mở ra sẽ rỗng"
                : undefined
            }
          >
            <Send size={13} strokeWidth={2} aria-hidden />
            Xuất bản bộ
          </Button>
        )}
        {canPublish && (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="quiet"
              onClick={() => onArchive(collection.status !== "archived")}
              disabled={busy}
            >
              {collection.status === "archived" ? "Bỏ lưu trữ" : "Lưu trữ"}
            </Button>
            <Button
              size="sm"
              variant="quiet"
              onClick={() => setConfirming(true)}
              disabled={busy}
              // Xoá bộ đề KHÔNG xoá đề trong nó, và endpoint từ chối khi bộ còn
              // đề — nói trước ở đây để người ta không bấm rồi mới biết.
              title={
                collection.test_count > 0
                  ? "Còn đề trong bộ — chuyển chúng sang bộ khác trước"
                  : undefined
              }
            >
              <Trash2 size={13} strokeWidth={1.75} aria-hidden />
            </Button>
          </div>
        )}
      </div>

      <Modal
        open={confirming}
        onClose={() => {
          setRefusal(null);
          setConfirming(false);
        }}
        title={`Xoá bộ đề ${collection.title}?`}
        // Cấp duy nhất mà database không chặn: xoá bộ đề chỉ gỡ liên kết, đề
        // vẫn còn — nhưng đề không thuộc bộ nào thì người học không thấy nữa.
        description="Bộ đề phải rỗng mới xoá được. Xoá bộ không xoá đề, nhưng đề không thuộc bộ nào thì người học không còn đường tới."
      >
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="destructive"
            onClick={async () => {
              const problem = await onDelete();
              if (problem === null) setConfirming(false);
              else setRefusal(problem);
            }}
            disabled={busy}
          >
            Xoá bộ đề
          </Button>
          <Button
            variant="quiet"
            onClick={() => {
              setRefusal(null);
              setConfirming(false);
            }}
            disabled={busy}
          >
            Huỷ
          </Button>
        </div>

        {refusal && (
          <div className="mt-3">
            <FieldError>{refusal}</FieldError>
            <div className="mt-2">
              <Button
                size="sm"
                variant="destructive"
                onClick={async () => {
                  const problem = await onDelete(true);
                  if (problem === null) setConfirming(false);
                }}
                disabled={busy}
                title="Xoá bộ đề cùng mọi đề, câu hỏi và lượt làm bài bên trong — chỉ dùng khi dọn dữ liệu thử"
              >
                Xoá cưỡng chế (mất đề và lịch sử làm bài)
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <div className="mt-3 space-y-2 border-l-2 border-rule pl-3">
        {tests.length === 0 ? (
          <p className="text-small text-ink-muted">Bộ này chưa có đề nào.</p>
        ) : (
          tests.map((test) => <TestRow key={test.id} test={test} />)
        )}
      </div>
    </Panel>
  );
}

function TestRow({ test }: { test: TestAdmin }) {
  return (
    <Link
      href={`/admin/tests/${test.slug}`}
      className="block rounded border border-rule bg-panel p-3 hover:border-rule-strong"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <FileText size={14} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        <p className="font-semibold">{test.title}</p>
        <PublishTag status={test.status} />
        <span className="font-data text-small text-ink-faint">{test.slug}</span>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-ink-muted">
        <span className="inline-flex items-center gap-1.5">
          <ClipboardList size={13} strokeWidth={1.75} aria-hidden />
          <span className="font-data tabular-nums">{test.question_count}</span> câu
        </span>
        {test.parts.map((part) => (
          <span
            key={part.part}
            className={cx("font-data", part.problem_count > 0 ? "text-alert" : "text-ink-muted")}
          >
            P{part.part} {part.published_count}/{part.question_count}
          </span>
        ))}
      </div>
    </Link>
  );
}
