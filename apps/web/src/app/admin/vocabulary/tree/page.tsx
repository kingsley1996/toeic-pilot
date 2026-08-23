"use client";

import {
  API_ROUTES,
  type TopicAdmin,
  type VocabularyCollectionAdmin,
  type VocabularyCollectionItemAdmin,
} from "@toeic-pilot/shared";
import { BookOpen, FolderTree, Library, Send, Tags } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { DestructiveButton } from "@/components/destructive-button";
import { Modal } from "@/components/modal";
import { AddChild, InlineRename, TreeEmpty, TreeNode } from "@/components/tree";
import {
  Alert,
  Button,
  EmptyState,
  Field,
  Input,
  Page,
  PageHeader,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Spinner,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Cây từ vựng: tuyển tập → cuốn sách → chủ đề.
 *
 * Cả ba tầng trên MỘT màn hình, và lồng vào nhau thật chứ không phải ba danh
 * sách phẳng chồng lên nhau như bản trước. Lúc dựng cây người ta tạo tuyển tập
 * rồi tạo ngay cuốn sách bên trong, rồi chủ đề bên trong cuốn — nên nút "thêm"
 * nằm TRONG nhánh mà nó thêm vào, và cái `<select>` "thuộc tuyển tập nào" của
 * bản cũ biến mất cùng với khả năng chọn nhầm.
 *
 * Chủ đề trước kia được tạo và xoá ở `/admin` còn xếp vào cuốn sách ở đây, tức
 * là tầng ba của cây bị chẻ làm đôi qua hai màn hình. Toàn bộ vòng đời của nó
 * chuyển về đây; `/admin` quay lại làm đúng việc của một trang tổng quan.
 */
export default function AdminVocabularyTreePage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [collections, setCollections] = useState<VocabularyCollectionAdmin[] | null>(null);
  const [items, setItems] = useState<VocabularyCollectionItemAdmin[]>([]);
  const [topics, setTopics] = useState<TopicAdmin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<TopicAdmin | null>(null);

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

  if (status !== "authenticated") {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  // Chủ đề chưa xếp vào cuốn nào: học viên không có đường tới chúng, nên nếu
  // màn quản trị cũng không hiện thì chúng biến mất khỏi tầm mắt mà vẫn nằm
  // trong database. Cùng lý do với khối "chưa thuộc bộ nào" ở /admin/tests.
  const unfiled = topics?.filter((topic) => topic.collection_item_id === null) ?? [];

  return (
    <Page>
      <PageHeader
        title="Cây từ vựng"
        description="Tuyển tập → cuốn sách → chủ đề. Xuất bản từ dưới lên: chủ đề và cuốn sách trước, rồi tới tuyển tập."
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
        <SectionHeader
          title="Tuyển tập"
          aside={
            <AddChild
              label="Thêm tuyển tập"
              fields={[
                { name: "slug", placeholder: "toeic", className: "max-w-[9rem]" },
                { name: "name", placeholder: "Từ vựng TOEIC" },
              ]}
              onSubmit={(values) =>
                void send(API_ROUTES.adminVocabularyCollections, "POST", values)
              }
            />
          }
        />

        {!collections && <SkeletonList rows={2} />}

        {collections?.length === 0 && (
          <EmptyState
            icon={FolderTree}
            title="Chưa có tuyển tập nào"
            description="Tạo một tuyển tập, rồi thêm cuốn sách bên trong nó, rồi chủ đề bên trong cuốn."
          />
        )}

        <div className="space-y-3">
          {collections?.map((collection) => {
            const books = items.filter((item) => item.collection_id === collection.id);
            return (
              <TreeNode
                key={collection.id}
                icon={Library}
                name={
                  <InlineRename
                    value={collection.name}
                    onSave={(name) =>
                      void send(API_ROUTES.adminVocabularyCollection(collection.id), "PATCH", {
                        name,
                      })
                    }
                  />
                }
                meta={
                  <>
                    <span className="font-data text-small text-ink-faint">/{collection.slug}</span>
                    <span className="font-data text-small text-ink-muted">
                      {collection.item_count} cuốn
                    </span>
                    <PublishTag status={collection.status} />
                  </>
                }
                actions={
                  <>
                    {collection.status !== "published" && (
                      <Button
                        size="sm"
                        disabled={!canPublish}
                        title={canPublish ? "Xuất bản tuyển tập" : "Chỉ admin mới xuất bản được"}
                        onClick={() =>
                          void send(
                            API_ROUTES.adminVocabularyCollectionPublish(collection.id),
                            "POST",
                          )
                        }
                      >
                        <Send size={13} strokeWidth={2} aria-hidden />
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
                  </>
                }
              >
                {books.length === 0 && <TreeEmpty>Tuyển tập này chưa có cuốn sách nào.</TreeEmpty>}

                {books.map((book) => {
                  const inBook = topics?.filter((t) => t.collection_item_id === book.id) ?? [];
                  return (
                    <TreeNode
                      key={book.id}
                      level={1}
                      icon={BookOpen}
                      name={
                        <InlineRename
                          value={book.name}
                          onSave={(name) =>
                            void send(API_ROUTES.adminVocabularyCollectionItem(book.id), "PATCH", {
                              name,
                            })
                          }
                        />
                      }
                      meta={
                        <>
                          <span className="font-data text-small text-ink-muted">
                            {book.topic_count} chủ đề
                          </span>
                          <PublishTag status={book.status} />
                        </>
                      }
                      actions={
                        <>
                          {book.status !== "published" && (
                            <Button
                              size="sm"
                              disabled={!canPublish}
                              title={
                                canPublish ? "Xuất bản cuốn sách" : "Chỉ admin mới xuất bản được"
                              }
                              onClick={() =>
                                void send(
                                  API_ROUTES.adminVocabularyCollectionItemPublish(book.id),
                                  "POST",
                                )
                              }
                            >
                              <Send size={13} strokeWidth={2} aria-hidden />
                              Xuất bản
                            </Button>
                          )}
                          <DestructiveButton
                            label="Xoá"
                            confirmLabel={`Xoá cuốn sách? ${book.topic_count} chủ đề bên trong sẽ quay về "chưa xếp".`}
                            disabled={!canPublish}
                            title={canPublish ? "Xoá cuốn sách này" : "Chỉ admin mới xoá được"}
                            onConfirm={() =>
                              void send(API_ROUTES.adminVocabularyCollectionItem(book.id), "DELETE")
                            }
                          />
                        </>
                      }
                    >
                      {inBook.length === 0 && <TreeEmpty>Cuốn này chưa có chủ đề nào.</TreeEmpty>}
                      {inBook.map((topic) => (
                        <TopicRow
                          key={topic.id}
                          topic={topic}
                          level={2}
                          canPublish={canPublish}
                          onSend={send}
                          onEdit={setEditing}
                        />
                      ))}
                      <div className="pt-0.5">
                        <AddChild
                          label="Thêm chủ đề"
                          fields={[
                            { name: "slug", placeholder: "business", className: "max-w-[9rem]" },
                            { name: "name", placeholder: "Kinh doanh" },
                          ]}
                          onSubmit={(values) =>
                            void send(API_ROUTES.adminTopics, "POST", {
                              ...values,
                              collection_item_id: book.id,
                            })
                          }
                        />
                      </div>
                    </TreeNode>
                  );
                })}

                <div className="pt-0.5">
                  <AddChild
                    label="Thêm cuốn sách"
                    fields={[{ name: "name", placeholder: "600 từ vựng TOEIC cơ bản" }]}
                    onSubmit={(values) =>
                      void send(API_ROUTES.adminVocabularyCollectionItems, "POST", {
                        ...values,
                        collection_id: collection.id,
                      })
                    }
                  />
                </div>
              </TreeNode>
            );
          })}
        </div>
      </section>

      {unfiled.length > 0 && (
        <section className="mt-10">
          <SectionHeader title="Chủ đề chưa xếp" />
          {/* Đổi cuốn là PATCH lên chính topic: "" = gỡ về "chưa xếp", không gửi
              = để nguyên — quy ước đó nằm phía API, ở đây chỉ cần gửi đúng giá trị. */}
          <p className="mb-3 text-small text-ink-muted">
            Chủ đề không nằm trong cuốn nào thì học viên không có đường tới. Chọn một cuốn để xếp nó
            vào cây.
          </p>
          <div className="space-y-2">
            {unfiled.map((topic) => (
              <TopicRow
                key={topic.id}
                topic={topic}
                level={1}
                canPublish={canPublish}
                onSend={send}
                onEdit={setEditing}
                assign={
                  <>
                    <label className="sr-only" htmlFor={`book-${topic.id}`}>
                      Cuốn sách của {topic.name}
                    </label>
                    <Select
                      id={`book-${topic.id}`}
                      value=""
                      onChange={(e) =>
                        void send(API_ROUTES.adminTopic(topic.id), "PATCH", {
                          collection_item_id: e.target.value,
                        })
                      }
                      className="max-w-56"
                    >
                      <option value="">(chọn cuốn sách)</option>
                      {items.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.collection_name} — {item.name}
                        </option>
                      ))}
                    </Select>
                  </>
                }
              />
            ))}
          </div>
        </section>
      )}

      {editing && (
        <TopicEditModal
          topic={editing}
          books={items}
          token={token ?? ""}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            if (token) refresh(token);
          }}
        />
      )}
    </Page>
  );
}

/**
 * Hàng chủ đề, dùng chung cho trong cây lẫn khối "chưa xếp".
 *
 * Khai báo ở phạm vi MODULE chứ không trong thân trang. Một component khai báo
 * bên trong component khác là một kiểu mới sau mỗi lần cha render, nên React
 * tháo cả hàng ra rồi dựng lại thay vì cập nhật nó — và cùng với hàng thì state
 * của `InlineRename` bên trong cũng mất. Hai cây trước kia đều dính lỗi này.
 */
function TopicRow({
  topic,
  level,
  canPublish,
  onSend,
  onEdit,
  assign,
}: {
  topic: TopicAdmin;
  level: 1 | 2;
  canPublish: boolean;
  onSend: (path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) => void;
  onEdit: (topic: TopicAdmin) => void;
  /** Ô chọn cuốn sách, chỉ có ở khối "chưa xếp". Nằm TRONG hàng chứ không cạnh
      nó: đặt bên ngoài thì hàng bị bóp lại và cụm nút của nó rớt xuống dòng hai
      — cùng một hàng chủ đề bỗng cao gấp đôi hàng bên trong cây. */
  assign?: ReactNode;
}) {
  return (
    <TreeNode
      level={level}
      icon={Tags}
      name={
        <InlineRename
          value={topic.name}
          onSave={(name) => onSend(API_ROUTES.adminTopic(topic.id), "PATCH", { name })}
        />
      }
      meta={
        <>
          <span className="font-data text-small text-ink-faint">/{topic.slug}</span>
          <span className="font-data text-small text-ink-muted">{topic.entry_count} từ</span>
          <PublishTag status={topic.status} />
        </>
      }
      actions={
        <>
          {assign}
          {topic.status !== "published" && (
            <Button
              size="sm"
              disabled={!canPublish}
              title={canPublish ? "Xuất bản chủ đề" : "Chỉ admin mới xuất bản được"}
              onClick={() =>
                onSend(API_ROUTES.adminTopic(topic.id), "PATCH", { status: "published" })
              }
            >
              <Send size={13} strokeWidth={2} aria-hidden />
              Xuất bản
            </Button>
          )}
          <Button size="sm" variant="quiet" onClick={() => onEdit(topic)}>
            Chi tiết
          </Button>
          <DestructiveButton
            label="Xoá"
            confirmLabel={
              topic.entry_count > 0
                ? `Xoá chủ đề? ${topic.entry_count} từ vẫn được giữ`
                : "Xoá chủ đề?"
            }
            disabled={!canPublish}
            title={canPublish ? "Xoá chủ đề này" : "Chỉ admin mới xoá được"}
            onConfirm={() => onSend(API_ROUTES.adminTopic(topic.id), "DELETE")}
          />
        </>
      }
    />
  );
}

/**
 * Slug, mô tả và cuốn sách của một chủ đề.
 *
 * Đổi tên là việc hay làm nhất nên nó ở ngay trên hàng; những thứ còn lại hiếm
 * hơn và một trong số đó (slug) làm hỏng link cũ của học viên, nên chúng nằm
 * sau một bước bấm có chỗ để nói điều đó ra.
 */
function TopicEditModal({
  topic,
  books,
  token,
  onClose,
  onSaved,
}: {
  topic: TopicAdmin;
  books: VocabularyCollectionItemAdmin[];
  token: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(topic.name);
  const [slug, setSlug] = useState(topic.slug);
  const [description, setDescription] = useState(topic.description ?? "");
  const [status, setStatus] = useState(topic.status);
  const [bookId, setBookId] = useState(topic.collection_item_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch<TopicAdmin>(API_ROUTES.adminTopic(topic.id), {
        method: "PATCH",
        token,
        body: JSON.stringify({
          name,
          slug,
          description: description.trim() === "" ? null : description,
          status,
          collection_item_id: bookId,
        }),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Sửa chủ đề “${topic.name}”`}
      description={`${topic.entry_count} từ đang gán vào chủ đề này.`}
    >
      <div className="space-y-4">
        <Field label="Tên hiển thị">
          <Input value={name} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Field label="Slug" hint="dùng trong URL — đổi slug làm link cũ của học viên 404">
          <Input value={slug} onChange={(event) => setSlug(event.target.value)} />
        </Field>
        <Field label="Mô tả" hint="để trống nếu không có">
          <Input value={description} onChange={(event) => setDescription(event.target.value)} />
        </Field>
        <Field label="Cuốn sách" hint="chưa xếp = học viên không có đường tới chủ đề này">
          <Select value={bookId} onChange={(event) => setBookId(event.target.value)}>
            <option value="">(chưa xếp)</option>
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.collection_name} — {book.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Trạng thái" hint="nháp = học viên không thấy chủ đề này">
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="published">published</option>
            <option value="draft">draft</option>
            <option value="archived">archived</option>
          </Select>
        </Field>

        {error && <Alert>{error}</Alert>}

        <div className="flex justify-end gap-2 border-t border-rule pt-4">
          <Button variant="secondary" onClick={onClose}>
            Huỷ
          </Button>
          <Button disabled={!name.trim() || !slug.trim() || busy} onClick={() => void save()}>
            {busy && <Spinner />}
            Lưu
          </Button>
        </div>
      </div>
    </Modal>
  );
}
