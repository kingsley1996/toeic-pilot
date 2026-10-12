"use client";

import { API_ROUTES, type BlogPostAdmin, type TocEntry } from "@toeic-pilot/shared";
import type { Editor } from "@tiptap/react";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { BlogEditor } from "@/components/blog-editor";
import {
  Alert,
  Button,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  Select,
  SkeletonList,
  Textarea,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const CATEGORIES = [
  { slug: "meo-lam-bai", label: "Mẹo làm bài" },
  { slug: "ngu-phap", label: "Ngữ pháp" },
  { slug: "tu-vung", label: "Từ vựng" },
  { slug: "kinh-nghiem", label: "Kinh nghiệm" },
  { slug: "thong-bao", label: "Thông báo" },
] as const;

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Soạn bài blog — dùng chung cho tạo mới và sửa (khác ở `postId`).
 * Thân bài là editor Tiptap (`BlogEditor`); lúc Lưu đọc `body_json` +
 * `body_html` từ editor, hai cột luôn đi cùng nhau (server từ chối nhận lẻ).
 */
export function BlogPostForm({ postId }: { postId: string | null }) {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const router = useRouter();
  const editorRef = useRef<Editor | null>(null);
  const [loaded, setLoaded] = useState(postId === null);
  const [post, setPost] = useState<BlogPostAdmin | null>(null);
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [excerpt, setExcerpt] = useState("");
  const [category, setCategory] = useState<string>("meo-lam-bai");
  const [tags, setTags] = useState("");
  const [cover, setCover] = useState("");
  const [author, setAuthor] = useState("ToeicPilot");
  const [relatedPart, setRelatedPart] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [license, setLicense] = useState("");
  const [attribution, setAttribution] = useState("");
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (postId === null || !token) return;
    apiFetch<BlogPostAdmin>(API_ROUTES.adminBlogPost(postId), { token })
      .then((loadedPost) => {
        setPost(loadedPost);
        setTitle(loadedPost.title);
        setSlug(loadedPost.slug);
        setSlugTouched(true);
        setExcerpt(loadedPost.excerpt);
        setCategory(loadedPost.category);
        setTags((loadedPost.tags ?? []).join(", "));
        setCover(loadedPost.cover_image_url ?? "");
        setAuthor(loadedPost.author_name);
        setRelatedPart(loadedPost.related_part?.toString() ?? "");
        setLoaded(true);
      })
      .catch(() => setFailure("Không tải được bài viết này."));
  }, [postId, token]);

  if (status !== "authenticated") {
    return (
      <Page className="max-w-5xl">
        <SkeletonList rows={6} />
      </Page>
    );
  }

  function readEditor(): { body_json: Record<string, unknown>; body_html: string } | null {
    const editor = editorRef.current;
    if (!editor || editor.getText().trim().length === 0) return null;
    return { body_json: editor.getJSON() as Record<string, unknown>, body_html: editor.getHTML() };
  }

  function payload() {
    const body = readEditor();
    if (!body) {
      setFailure("Thân bài còn trống.");
      return null;
    }
    const related = relatedPart.trim();
    return {
      title: title.trim(),
      slug: slug.trim(),
      excerpt: excerpt.trim(),
      category,
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      cover_image_url: cover.trim() || null,
      author_name: author.trim() || "ToeicPilot",
      related_part: related ? Number(related) : null,
      ...body,
    };
  }

  async function save(goBack: boolean) {
    if (!token) return;
    const data = payload();
    if (!data) return;
    setSaving(true);
    setFailure(null);
    try {
      if (postId === null) {
        const created = await apiFetch<{ id: string }>(API_ROUTES.adminBlogPosts, {
          method: "POST",
          token,
          body: JSON.stringify(data),
        });
        router.push(goBack ? "/admin/blog" : `/admin/blog/${created.id}`);
      } else {
        await apiFetch(API_ROUTES.adminBlogPost(postId), {
          method: "PATCH",
          token,
          body: JSON.stringify(data),
        });
        if (goBack) router.push("/admin/blog");
        else setFailure(null);
      }
    } catch (err) {
      setFailure(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setSaving(false);
    }
  }

  async function setPublished(published: boolean) {
    if (!token || postId === null) return;
    // Publish khi còn sửa dang dở thì cổng server từ chối — lưu trước đã.
    const data = payload();
    if (!data) return;
    setSaving(true);
    setFailure(null);
    try {
      await apiFetch(API_ROUTES.adminBlogPost(postId), {
        method: "PATCH",
        token,
        body: JSON.stringify(data),
      });
      const updated = await apiFetch<BlogPostAdmin>(
        published
          ? API_ROUTES.adminBlogPostPublish(postId)
          : API_ROUTES.adminBlogPostUnpublish(postId),
        { method: "POST", token },
      );
      setPost(updated);
    } catch (err) {
      setFailure(err instanceof ApiError ? err.message : "Không đổi trạng thái được.");
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) {
    return (
      <Page className="max-w-5xl">
        <SkeletonList rows={6} />
      </Page>
    );
  }

  const toc: TocEntry[] = post?.toc ?? [];
  const isPublished = post?.status === "published";

  return (
    <Page className="max-w-6xl">
      <Link
        href="/admin/blog"
        className="mb-3 inline-flex items-center gap-1.5 text-small text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={13} strokeWidth={2} aria-hidden />
        Quay lại danh sách bài
      </Link>

      <PageHeader
        eyebrow={postId === null ? "Bài viết mới" : isPublished ? "Đã xuất bản" : "Bản nháp"}
        title={title || "(chưa đặt tên)"}
      />

      {failure && (
        <div className="mb-4">
          <Alert>{failure}</Alert>
        </div>
      )}

      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <Field label="Tiêu đề">
          <Input
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              if (!slugTouched) setSlug(slugify(e.target.value));
            }}
          />
        </Field>
        <Field label="Slug (khóa sau khi xuất bản)">
          <Input
            value={slug}
            disabled={isPublished}
            onChange={(e) => {
              setSlug(e.target.value);
              setSlugTouched(true);
            }}
            className="font-data"
          />
        </Field>
      </div>

      <div className="mb-4">
        <Field label={`Sapo (${excerpt.trim().length}/160 — vừa là meta description)`}>
          <Textarea
            value={excerpt}
            onChange={(e) => setExcerpt(e.target.value)}
            rows={2}
            placeholder="1–2 câu tóm tắt, viết tay, không copy câu đầu thân bài."
          />
        </Field>
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-4">
        <Field label="Chuyên mục">
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Tags (phẩy ngăn cách)">
          <Input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="part-3, listening"
          />
        </Field>
        <Field label="Tác giả">
          <Input value={author} onChange={(e) => setAuthor(e.target.value)} />
        </Field>
        <Field label="Part liên quan (trống = không gắn)">
          <Select value={relatedPart} onChange={(e) => setRelatedPart(e.target.value)}>
            <option value="">—</option>
            {[1, 2, 3, 4, 5, 6, 7].map((p) => (
              <option key={p} value={p}>
                Part {p}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="mb-4">
        <Field label="Ảnh bìa (URL)">
          <Input
            value={cover}
            onChange={(e) => setCover(e.target.value)}
            placeholder="https://…"
            className="font-data"
          />
        </Field>
        {cover.trim() && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={cover.trim()} alt="" className="mt-2 max-h-48 rounded border border-rule" />
        )}
      </div>

      <Panel className="mb-4 p-4">
        <p className="mb-2 text-small font-semibold">Xuất xứ ảnh chèn trong bài</p>
        <p className="mb-2 text-label text-ink-muted">
          Ba trường NOT NULL ở `image_asset` — khai một lần cho cả bài, mỗi ảnh tự lấy alt từ tên
          file (sửa được trong toolbar khi bấm vào ảnh).
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Nguồn ảnh">
            <Input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://… hoặc 'tự chụp'"
            />
          </Field>
          <Field label="Giấy phép">
            <Input
              value={license}
              onChange={(e) => setLicense(e.target.value)}
              placeholder="CC-BY / tự sở hữu…"
            />
          </Field>
          <Field label="Ghi công">
            <Input
              value={attribution}
              onChange={(e) => setAttribution(e.target.value)}
              placeholder="Tên tác giả/nguồn"
            />
          </Field>
        </div>
      </Panel>

      <Field label="Thân bài">
        <BlogEditor
          initialDoc={(post?.body_json ?? null) as Record<string, unknown> | null}
          editorRef={editorRef}
          token={token}
          provenance={{ source_url: sourceUrl, license, attribution, alt_text: null }}
        />
      </Field>

      {toc.length > 0 && (
        <p className="mt-2 text-label text-ink-faint">
          Mục lục tự sinh: {toc.map((t) => t.text).join(" · ")}
        </p>
      )}

      <div className="sticky bottom-0 -mx-4 mt-6 flex flex-wrap items-center justify-end gap-2 border-t border-rule bg-ground/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <Button variant="quiet" onClick={() => router.push("/admin/blog")}>
          Huỷ
        </Button>
        {postId !== null && canPublish && !isPublished && (
          <Button variant="quiet" disabled={saving} onClick={() => void setPublished(true)}>
            Xuất bản
          </Button>
        )}
        {postId !== null && canPublish && isPublished && (
          <Button variant="quiet" disabled={saving} onClick={() => void setPublished(false)}>
            Gỡ xuống
          </Button>
        )}
        <Button
          disabled={saving || !title.trim() || !slug.trim() || !excerpt.trim()}
          onClick={() => void save(false)}
        >
          {saving ? "Đang lưu…" : "Lưu"}
        </Button>
        <Button
          variant="quiet"
          disabled={saving || !title.trim() || !slug.trim() || !excerpt.trim()}
          onClick={() => void save(true)}
        >
          Lưu và về danh sách
        </Button>
      </div>
    </Page>
  );
}
