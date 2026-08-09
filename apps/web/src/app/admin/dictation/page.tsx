"use client";

import {
  API_ROUTES,
  type CommitResult,
  type DictationAdmin,
  type DictationParseResponse,
  type DictationStoryAdmin,
  type TopicAdmin,
} from "@toeic-pilot/shared";
import { Archive, ArchiveRestore, ArrowDown, ArrowUp, Headphones, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BackfillHint, ParsePreview } from "@/components/admin-bits";
import { DestructiveButton } from "@/components/destructive-button";
import {
  Alert,
  AudioTag,
  Button,
  EmptyState,
  Field,
  Page,
  PageHeader,
  Panel,
  PublishTag,
  SectionHeader,
  Select,
  SkeletonList,
  Spinner,
  Textarea,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const PLACEHOLDER = `The quarterly report is due before the end of the month.
Please submit your expense claims to the finance department.`;

export default function AdminDictationPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<DictationParseResponse | null>(null);
  const [topics, setTopics] = useState<TopicAdmin[]>([]);
  const [topicId, setTopicId] = useState("");
  const [stories, setStories] = useState<DictationStoryAdmin[]>([]);
  const [storyId, setStoryId] = useState("");
  const [items, setItems] = useState<DictationAdmin[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((t: string) => {
    apiFetch<DictationAdmin[]>(API_ROUTES.adminDictation, { token: t })
      .then(setItems)
      .catch(() => setError("Không tải được danh sách câu."));
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<TopicAdmin[]>(API_ROUTES.adminTopics, { token })
      .then(setTopics)
      .catch(() => {});
    apiFetch<DictationStoryAdmin[]>(API_ROUTES.adminDictationStories, { token })
      .then(setStories)
      .catch(() => {});
    refresh(token);
  }, [token, refresh]);

  async function parse() {
    if (!token) return;
    setNotice(null);
    setError(null);
    setBusy(true);
    try {
      setParsed(
        await apiFetch<DictationParseResponse>(API_ROUTES.adminDictationParse, {
          method: "POST",
          token,
          body: JSON.stringify({ raw_text: raw }),
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không phân tích được.");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!token || !parsed) return;
    setBusy(true);
    try {
      const result = await apiFetch<CommitResult>(API_ROUTES.adminDictation, {
        method: "POST",
        token,
        body: JSON.stringify({
          rows: parsed.rows,
          topic_id: topicId || null,
          story_id: storyId || null,
        }),
      });
      setNotice(
        `Đã lưu ${result.created} câu ở dạng nháp${storyId ? ", đánh số theo đúng thứ tự đã dán" : ""}. Chúng chưa có audio — bước tiếp theo là sinh.`,
      );
      setParsed(null);
      setRaw("");
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  async function send(path: string, method: "PATCH" | "DELETE" | "POST", body?: unknown) {
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
      // Máy chủ trả 409 khi câu đã có người làm. Thông điệp gốc bằng tiếng Anh
      // và chỉ tới một thao tác — nói bằng ngôn ngữ của màn hình này, và chỉ
      // đúng cái nút đang nằm ngay cạnh, thì người dùng không phải đi tìm.
      if (err instanceof ApiError && err.status === 409 && method === "DELETE") {
        setError(
          "Không xoá được: đã có học viên làm câu này, và xoá đi sẽ làm mất lịch sử của họ. " +
            "Dùng nút Lưu trữ ngay cạnh — câu sẽ biến mất khỏi phần học nhưng lịch sử vẫn còn.",
        );
        return;
      }
      setError(err instanceof ApiError ? err.message : "Thao tác không thành công.");
    }
  }

  /**
   * Đổi chỗ hai câu liền nhau trong một bài.
   *
   * Gửi lên CẢ danh sách theo thứ tự mới chứ không gửi "đổi A với B": server gán
   * lại 1..N trong một giao dịch, nên không có khoảnh khắc nào hai câu cùng mang
   * một số.
   */
  function move(storyId: string, ids: string[], from: number, to: number) {
    if (to < 0 || to >= ids.length) return;
    const next = [...ids];
    [next[from], next[to]] = [next[to], next[from]];
    void send(API_ROUTES.adminDictationStoryReorder(storyId), "POST", { item_ids: next });
  }

  async function publish(id: string) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(API_ROUTES.adminDictationPublish(id), { method: "POST", token });
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không publish được.");
    }
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
        title="Câu nghe"
        description="Transcript vừa là nguồn sinh audio vừa là đáp án chấm bài — sửa nó là audio cũ thành sai."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-4">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}

      <Panel className="p-5">
        <Field label="Dán hàng loạt" hint="Mỗi dòng một câu">
          <Textarea
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            rows={6}
            placeholder={PLACEHOLDER}
          />
        </Field>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <Button variant="secondary" disabled={!raw.trim() || busy} onClick={() => void parse()}>
            {busy && <Spinner />}
            Kiểm tra
          </Button>
          {/* Chọn bài thì mỗi dòng dán vào thành một câu CÓ THỨ TỰ trong bài
              đó, nối tiếp sau những câu đã có. Đó là cách một bài văn được nhập:
              dán cả bài, mỗi dòng một câu. */}
          <Field label="Thuộc bài nào" hint="mỗi dòng thành một câu, theo đúng thứ tự đã dán">
            <Select value={storyId} onChange={(event) => setStoryId(event.target.value)}>
              <option value="">(câu lẻ, không thuộc bài nào)</option>
              {stories.map((story) => (
                <option key={story.id} value={story.id}>
                  {story.topic_name} / {story.section_name} / {story.title}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Gán vào chủ đề (từ vựng)">
            <Select value={topicId} onChange={(event) => setTopicId(event.target.value)}>
              <option value="">(không gán)</option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.name}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Panel>

      {parsed && (
        <>
          <ParsePreview parsed={parsed} render={(row) => <span>{row.transcript}</span>} />
          <Button
            className="mt-4"
            disabled={parsed.ok_count === 0 || busy}
            onClick={() => void commit()}
          >
            {busy && <Spinner />}
            Lưu {parsed.ok_count} câu ở dạng nháp
          </Button>
        </>
      )}

      <section className="mt-12">
        <SectionHeader title="Tất cả câu" />
        {!items && <SkeletonList rows={3} />}

        {items?.length === 0 && (
          <EmptyState
            icon={Headphones}
            title="Chưa có câu nào"
            description="Dán vài câu ở trên để bắt đầu."
          />
        )}

        <div className="space-y-2">
          {items?.map((item) => (
            <Panel key={item.id} className="px-4 py-3">
              {/* Hai dòng, không phải một: nhét câu chữ và sáu ô điều khiển lên
                  cùng một hàng flex làm cột chữ bị bóp xuống còn mỗi dòng một
                  từ. Câu là thứ cần đọc, nên nó được cả chiều ngang. */}
              <div className="flex items-baseline gap-2">
                {item.position !== null && item.position !== undefined && (
                  <span className="shrink-0 font-data text-small text-ink-faint">
                    {item.position}.
                  </span>
                )}
                <p className="min-w-0 flex-1 text-body">{item.transcript}</p>
                <span className="flex shrink-0 items-center gap-2">
                  <PublishTag status={item.status} />
                  <AudioTag state={item.audio_state} />
                </span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                {/* Đổi thứ tự chỉ có nghĩa bên trong một bài. */}
                {item.story_id &&
                  (() => {
                    const siblings = (items ?? [])
                      .filter((other) => other.story_id === item.story_id)
                      .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
                    const ids = siblings.map((other) => other.id);
                    const index = ids.indexOf(item.id);
                    return (
                      <span className="flex gap-0.5">
                        <Button
                          size="sm"
                          variant="quiet"
                          aria-label="Chuyển lên"
                          disabled={index <= 0}
                          onClick={() => move(item.story_id as string, ids, index, index - 1)}
                        >
                          <ArrowUp size={14} strokeWidth={2} aria-hidden />
                        </Button>
                        <Button
                          size="sm"
                          variant="quiet"
                          aria-label="Chuyển xuống"
                          disabled={index < 0 || index >= ids.length - 1}
                          onClick={() => move(item.story_id as string, ids, index, index + 1)}
                        >
                          <ArrowDown size={14} strokeWidth={2} aria-hidden />
                        </Button>
                      </span>
                    );
                  })()}

                {/* Chuyển sang bài khác, hoặc gỡ ra thành câu lẻ. Chuỗi rỗng nói
                    rõ "gỡ ra" — với PATCH thì bỏ trống và null là hai ý khác
                    nhau mà JSON không phân biệt được. */}
                <Select
                  aria-label="Thuộc bài nào"
                  value={item.story_id ?? ""}
                  onChange={(event) =>
                    void send(API_ROUTES.adminDictationItem(item.id), "PATCH", {
                      story_id: event.target.value,
                    })
                  }
                  className="w-auto max-w-[18rem] text-small"
                >
                  <option value="">(câu lẻ)</option>
                  {stories.map((story) => (
                    <option key={story.id} value={story.id}>
                      {story.section_name} / {story.title}
                    </option>
                  ))}
                </Select>

                <span className="ml-auto flex items-center gap-2">
                  {item.status !== "published" && (
                    <Button
                      size="sm"
                      disabled={!item.publishable || !canPublish}
                      onClick={() => void publish(item.id)}
                      title={
                        !canPublish
                          ? "Chỉ admin mới publish được"
                          : item.publishable
                            ? "Xuất bản câu này"
                            : "Audio chưa khớp với transcript"
                      }
                    >
                      <Send size={14} strokeWidth={2} aria-hidden />
                      Xuất bản
                    </Button>
                  )}
                  {/* Lưu trữ là đường lui cho câu đã có người học: gỡ khỏi tầm
                      mắt học viên mà không làm mồ côi lịch sử làm bài của họ.
                      Nó phải nằm NGAY CẠNH nút Xoá, vì đó là chỗ người dùng
                      đang đứng khi bị từ chối xoá. */}
                  {item.status === "archived" ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      title="Đưa về nháp để sửa hoặc xuất bản lại"
                      onClick={() =>
                        void send(API_ROUTES.adminDictationItem(item.id), "PATCH", {
                          status: "draft",
                        })
                      }
                    >
                      <ArchiveRestore size={14} strokeWidth={2} aria-hidden />
                      Bỏ lưu trữ
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      title="Ẩn khỏi phần học, giữ nguyên lịch sử làm bài"
                      onClick={() =>
                        void send(API_ROUTES.adminDictationItem(item.id), "PATCH", {
                          status: "archived",
                        })
                      }
                    >
                      <Archive size={14} strokeWidth={2} aria-hidden />
                      Lưu trữ
                    </Button>
                  )}
                  <DestructiveButton
                    label="Xoá"
                    confirmLabel="Xoá câu này?"
                    disabled={!canPublish}
                    title={
                      canPublish
                        ? "Xoá hẳn. Câu đã có người làm thì không xoá được — hãy lưu trữ."
                        : "Chỉ admin mới xoá được"
                    }
                    onConfirm={() => void send(API_ROUTES.adminDictationItem(item.id), "DELETE")}
                  />
                </span>
              </div>
            </Panel>
          ))}
        </div>
      </section>

      <div className="mt-12">
        <BackfillHint />
      </div>
    </Page>
  );
}
