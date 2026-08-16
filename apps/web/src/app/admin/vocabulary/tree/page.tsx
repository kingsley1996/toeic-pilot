"use client";

import {
  API_ROUTES,
  type TopicAdmin,
  type VocabularyCollectionAdmin,
  type VocabularyCollectionItemAdmin,
} from "@toeic-pilot/shared";
import { Check, Pencil, Send, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { DestructiveButton } from "@/components/destructive-button";
import {
  Alert,
  Button,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Cây từ vựng: tuyển tập → cuốn sách → chủ đề.
 *
 * Ba tầng trên một màn hình như `/admin/dictation/tree`: lúc dựng cây người ta tạo
 * tuyển tập rồi tạo ngay cuốn sách bên trong, rồi gán chủ đề vào cuốn sách. Bắt
 * họ đi lại giữa ba trang là biến một thao tác liền mạch thành ba.
 */
export default function AdminVocabularyTreePage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [collections, setCollections] = useState<VocabularyCollectionAdmin[] | null>(null);
  const [items, setItems] = useState<VocabularyCollectionItemAdmin[]>([]);
  const [topics, setTopics] = useState<TopicAdmin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; value: string } | null>(null);

  const [collectionForm, setCollectionForm] = useState({ slug: "", name: "" });
  const [itemForm, setItemForm] = useState({ collection_id: "", name: "" });

  const refresh = useCallback((t: string) => {
    void apiFetch<VocabularyCollectionAdmin[]>(API_ROUTES.adminVocabularyCollections, { token: t })
      .then(setCollections)
      .catch(() => setError("Không tải được cây từ vựng."));
    void apiFetch<VocabularyCollectionItemAdmin[]>(API_ROUTES.adminVocabularyCollectionItems, {
      token: t,
    })
      .then(setItems)
      .catch(() => {});
    void apiFetch<TopicAdmin[]>(API_ROUTES.adminTopics, { token: t })
      .then(setTopics)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  async function send(path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(path, {
        method,
        token,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Thao tác không thành công.");
    }
  }

  /** Ô sửa tên tại chỗ: đổi tên là thao tác hay dùng nhất, không đáng mở trang khác. */
  function NameCell({
    id,
    name,
    save,
  }: {
    id: string;
    name: string;
    save: (value: string) => void;
  }) {
    if (editing?.id !== id) {
      return (
        <>
          <span className="font-semibold">{name}</span>
          <Button
            size="sm"
            variant="quiet"
            aria-label={`Sửa tên ${name}`}
            title="Sửa tên"
            onClick={() => setEditing({ id, value: name })}
          >
            <Pencil size={14} strokeWidth={2} aria-hidden />
          </Button>
        </>
      );
    }
    return (
      <span className="flex min-w-0 flex-1 items-center gap-1">
        <Input
          value={editing.value}
          autoFocus
          onChange={(e) => setEditing({ id, value: e.target.value })}
          onKeyDown={(e) => {
            // Bỏ qua Enter khi bộ gõ đang ghép chữ: Telex/VNI thì Enter giữa chừng
            // một từ là phím XÁC NHẬN của bộ gõ, không phải phím lưu.
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter" && editing.value.trim()) save(editing.value.trim());
            if (e.key === "Escape") setEditing(null);
          }}
          className="max-w-xs"
        />
        <Button
          size="sm"
          aria-label="Lưu tên"
          disabled={!editing.value.trim()}
          onClick={() => save(editing.value.trim())}
        >
          <Check size={14} strokeWidth={2} aria-hidden />
        </Button>
        <Button size="sm" variant="quiet" aria-label="Huỷ sửa" onClick={() => setEditing(null)}>
          <X size={14} strokeWidth={2} aria-hidden />
        </Button>
      </span>
    );
  }

  if (status !== "authenticated") {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="Cây từ vựng"
        description="Tuyển tập → cuốn sách → chủ đề. Xuất bản từ dưới lên: cuốn sách và chủ đề trước, rồi tới tuyển tập."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {/* Học viên chỉ thấy một cuốn sách khi CẢ hai tầng cha đều đã xuất bản —
          xuất bản từ dưới lên là ràng buộc thật, không phải lời khuyên. */}
      <Alert tone="info">
        Học viên chỉ thấy cuốn sách khi cả cuốn sách và tuyển tập của nó đều đã xuất bản.
      </Alert>

      <section className="mt-8">
        <SectionHeader title="Tuyển tập" />
        <Panel className="p-4">
          <div className="grid gap-3 sm:grid-cols-[10rem_1fr_auto] sm:items-end">
            <Field label="Slug" hint="dùng trong URL">
              <Input
                value={collectionForm.slug}
                onChange={(e) => setCollectionForm({ ...collectionForm, slug: e.target.value })}
                placeholder="toeic"
              />
            </Field>
            <Field label="Tên hiển thị">
              <Input
                value={collectionForm.name}
                onChange={(e) => setCollectionForm({ ...collectionForm, name: e.target.value })}
                placeholder="Từ vựng TOEIC"
              />
            </Field>
            <Button
              disabled={!collectionForm.slug.trim() || !collectionForm.name.trim()}
              onClick={() => {
                void send(API_ROUTES.adminVocabularyCollections, "POST", collectionForm);
                setCollectionForm({ slug: "", name: "" });
              }}
            >
              Thêm tuyển tập
            </Button>
          </div>
        </Panel>

        {!collections && <SkeletonList rows={2} />}
        <div className="mt-3 space-y-2">
          {collections?.map((collection) => (
            <Panel key={collection.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <NameCell
                id={collection.id}
                name={collection.name}
                save={(value) => {
                  setEditing(null);
                  void send(API_ROUTES.adminVocabularyCollection(collection.id), "PATCH", {
                    name: value,
                  });
                }}
              />
              <span className="font-data text-small text-ink-faint">/{collection.slug}</span>
              <span className="font-data text-small text-ink-muted">
                {collection.item_count} cuốn
              </span>
              <span className="ml-auto flex items-center gap-2">
                <PublishTag status={collection.status} />
                {collection.status !== "published" && (
                  <Button
                    size="sm"
                    disabled={!canPublish}
                    title={canPublish ? "Xuất bản tuyển tập" : "Chỉ admin mới xuất bản được"}
                    onClick={() =>
                      void send(API_ROUTES.adminVocabularyCollectionPublish(collection.id), "POST")
                    }
                  >
                    <Send size={14} strokeWidth={2} aria-hidden />
                    Xuất bản
                  </Button>
                )}
                <DestructiveButton
                  label="Xoá"
                  confirmLabel={`Xoá cả ${collection.item_count} cuốn sách? Chủ đề bên trong vẫn được giữ.`}
                  disabled={!canPublish}
                  title={
                    canPublish
                      ? "Xoá tuyển tập. Từ vựng vẫn được giữ lại."
                      : "Chỉ admin mới xoá được"
                  }
                  onConfirm={() =>
                    void send(API_ROUTES.adminVocabularyCollection(collection.id), "DELETE")
                  }
                />
              </span>
            </Panel>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Cuốn sách" />
        <Panel className="p-4">
          <div className="grid gap-3 sm:grid-cols-[14rem_1fr_auto] sm:items-end">
            <Field label="Thuộc tuyển tập">
              <Select
                value={itemForm.collection_id}
                onChange={(e) => setItemForm({ ...itemForm, collection_id: e.target.value })}
              >
                <option value="">(chọn tuyển tập)</option>
                {collections?.map((collection) => (
                  <option key={collection.id} value={collection.id}>
                    {collection.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Tên cuốn sách">
              <Input
                value={itemForm.name}
                onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })}
                placeholder="600 từ vựng TOEIC cơ bản"
              />
            </Field>
            <Button
              disabled={!itemForm.collection_id || !itemForm.name.trim()}
              onClick={() => {
                void send(API_ROUTES.adminVocabularyCollectionItems, "POST", itemForm);
                setItemForm({ collection_id: "", name: "" });
              }}
            >
              Thêm cuốn sách
            </Button>
          </div>
        </Panel>

        {items.length > 0 && (
          <div className="mt-3 space-y-2">
            {items.map((item) => (
              <Panel key={item.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <NameCell
                  id={item.id}
                  name={item.name}
                  save={(value) => {
                    setEditing(null);
                    void send(API_ROUTES.adminVocabularyCollectionItem(item.id), "PATCH", {
                      name: value,
                    });
                  }}
                />
                <span className="font-data text-small text-ink-muted">
                  {item.collection_name} · {item.topic_count} chủ đề
                </span>
                <span className="ml-auto flex items-center gap-2">
                  <PublishTag status={item.status} />
                  {item.status !== "published" && (
                    <Button
                      size="sm"
                      disabled={!canPublish}
                      title={canPublish ? "Xuất bản cuốn sách" : "Chỉ admin mới xuất bản được"}
                      onClick={() =>
                        void send(API_ROUTES.adminVocabularyCollectionItemPublish(item.id), "POST")
                      }
                    >
                      <Send size={14} strokeWidth={2} aria-hidden />
                      Xuất bản
                    </Button>
                  )}
                  <DestructiveButton
                    label="Xoá"
                    confirmLabel={`Xoá cuốn sách? ${item.topic_count} chủ đề bên trong sẽ quay về "chưa xếp".`}
                    disabled={!canPublish}
                    title={canPublish ? "Xoá cuốn sách này" : "Chỉ admin mới xoá được"}
                    onConfirm={() =>
                      void send(API_ROUTES.adminVocabularyCollectionItem(item.id), "DELETE")
                    }
                  />
                </span>
              </Panel>
            ))}
          </div>
        )}
      </section>

      <section className="mt-10">
        <SectionHeader title="Xếp chủ đề vào cuốn sách" />
        {/* Đổi cuốn là PATCH lên chính topic: "" = gỡ về "chưa xếp", không gửi = để
            nguyên — quy ước đó nằm phía API, ở đây chỉ cần gửi giá trị đúng. */}
        {!topics && <SkeletonList rows={2} />}
        <div className="mt-3 space-y-2">
          {topics?.map((topic) => (
            <Panel key={topic.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="font-semibold">{topic.name}</span>
              <span className="font-data text-small text-ink-faint">{topic.entry_count} từ</span>
              <div className="ml-auto flex items-center gap-2">
                <label className="sr-only" htmlFor={`book-${topic.id}`}>
                  Cuốn sách của {topic.name}
                </label>
                <Select
                  id={`book-${topic.id}`}
                  value={topic.collection_item_id ?? ""}
                  onChange={(e) =>
                    void send(API_ROUTES.adminTopic(topic.id), "PATCH", {
                      collection_item_id: e.target.value,
                    })
                  }
                  className="max-w-64"
                >
                  <option value="">(chưa xếp)</option>
                  {items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.collection_name} — {item.name}
                    </option>
                  ))}
                </Select>
              </div>
            </Panel>
          ))}
        </div>
      </section>
    </Page>
  );
}
