"use client";

import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import { TableKit } from "@tiptap/extension-table";
import Underline from "@tiptap/extension-underline";
import CharacterCount from "@tiptap/extension-character-count";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  CodeXml,
  ImagePlus,
  Italic,
  Link2,
  Link2Off,
  List,
  ListOrdered,
  Minus,
  Quote,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Table,
  Underline as UnderlineIcon,
  Undo2,
} from "lucide-react";
import { useRef, useState, type MutableRefObject } from "react";

import { uploadImage, type ImageProvenance } from "@/lib/image-upload";

/**
 * Editor soạn bài blog (SPEC-BLOG §3): toolbar đầy đủ, không H1 (H1 duy nhất
 * là title bài — luật SEO). Ảnh chèn bằng upload thật qua luồng
 * ticket→confirm có sẵn, kèm kích thước chống CLS; caption lấy từ `title`
 * của ảnh lúc hiển thị.
 *
 * Cha đọc nội dung lúc bấm Lưu qua `editorRef` — không onChange mỗi phím gõ,
 * tài liệu dài mà setState lên cha theo từng ký tự là lag gõ.
 */
export function BlogEditor({
  initialDoc,
  editorRef,
  token,
  provenance,
}: {
  initialDoc: Record<string, unknown> | null;
  editorRef: MutableRefObject<Editor | null>;
  token: string | null;
  provenance: ImageProvenance;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const editor = useEditor(
    {
      immediatelyRender: false,
      extensions: [
        StarterKit.configure({ heading: { levels: [2, 3] } }),
        Underline,
        Link.configure({ openOnClick: false }),
        Image.configure({ inline: false }),
        TextAlign.configure({ types: ["heading", "paragraph"] }),
        TableKit,
        CharacterCount,
      ],
      content: initialDoc ?? undefined,
      editorProps: {
        attributes: { class: "blog-edit-area" },
      },
      onCreate: ({ editor }) => {
        editorRef.current = editor;
      },
      onDestroy: () => {
        editorRef.current = null;
      },
    },
    [],
  );

  async function insertImage(file: File) {
    if (!editor || !token) return;
    if (
      !provenance.source_url.trim() ||
      !provenance.license.trim() ||
      !provenance.attribution.trim()
    ) {
      setUploadError("Khai xuất xứ ảnh (nguồn + giấy phép + ghi công) ở form trước khi chèn ảnh.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const name = file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
      const asset = await uploadImage(file, { ...provenance, alt_text: name }, token);
      editor
        .chain()
        .focus()
        .setImage({ src: asset.url, alt: name, width: asset.width, height: asset.height })
        .run();
    } catch {
      setUploadError("Không tải được ảnh lên.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="overflow-hidden rounded border border-rule-strong bg-panel">
      {editor && <Toolbar editor={editor} onImageClick={() => fileRef.current?.click()} />}
      <EditorContent editor={editor} />
      <div className="flex items-center justify-between gap-2 border-t border-rule px-3 py-1.5">
        <p className="text-label text-ink-faint" aria-live="polite">
          {uploading ? "Đang tải ảnh…" : <WordCount editor={editor} />}
        </p>
        {uploadError && <p className="text-label text-danger">{uploadError}</p>}
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        aria-hidden
        tabIndex={-1}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void insertImage(file);
        }}
      />
      {/* Sống ở đây (ngoài Toolbar) để DOM gọn, bấm qua callback. */}
    </div>
  );
}

function WordCount({ editor }: { editor: Editor | null }) {
  const state = useEditorState({
    editor,
    selector: (ctx) => ({ words: ctx.editor?.storage.characterCount.words() ?? 0 }),
  });
  return (
    <span>
      <span className="font-data">{state?.words ?? 0}</span> từ
    </span>
  );
}

function ToolButton({
  editor,
  active,
  disabled,
  title,
  onClick,
  children,
}: {
  editor: Editor;
  active?: (e: Editor) => boolean;
  disabled?: (e: Editor) => boolean;
  title: string;
  onClick: (e: Editor) => void;
  children: React.ReactNode;
}) {
  const state = useEditorState({
    editor,
    selector: (ctx) => ({
      isActive: active?.(ctx.editor) ?? false,
      isDisabled: disabled?.(ctx.editor) ?? false,
    }),
  });
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={state.isActive}
      disabled={state.isDisabled}
      // Giữ focus + selection trong editor khi bấm toolbar: không có nó thì
      // mỗi cú bấm đánh rơi con trỏ, và chữ gõ tiếp theo rơi ra ngoài bài
      // (cách chữa chuẩn của Tiptap, không phải mẹo riêng).
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => onClick(editor)}
      className={`rounded p-1.5 hover:bg-recess disabled:opacity-30 ${
        state.isActive ? "bg-recess text-accent" : "text-ink-muted"
      }`}
    >
      {children}
    </button>
  );
}

function Toolbar({ editor, onImageClick }: { editor: Editor; onImageClick: () => void }) {
  const [linkUrl, setLinkUrl] = useState("");
  const linkActive = useEditorState({
    editor,
    selector: (ctx) => ctx.editor.isActive("link"),
  });
  const inTable = useEditorState({
    editor,
    selector: (ctx) => ctx.editor.isActive("table"),
  });
  const imageActive = useEditorState({
    editor,
    selector: (ctx) => ctx.editor.isActive("image"),
  });
  const [imgAlt, setImgAlt] = useState("");
  const [imgCaption, setImgCaption] = useState("");

  function applyLink() {
    const url = linkUrl.trim();
    if (!url) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().setLink({ href: url, target: "_blank" }).run();
    setLinkUrl("");
  }

  function applyImageMeta() {
    editor
      .chain()
      .focus()
      .updateAttributes("image", { alt: imgAlt, title: imgCaption || null })
      .run();
  }

  const icon = { size: 15, strokeWidth: 2 } as const;
  const can = (fn: (e: Editor) => boolean) => (e: Editor) => !fn(e);

  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-rule bg-ground px-2 py-1.5">
      <ToolButton
        editor={editor}
        title="Hoàn tác"
        disabled={can((e) => e.can().undo())}
        onClick={(e) => void e.chain().focus().undo().run()}
      >
        <Undo2 {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Làm lại"
        disabled={can((e) => e.can().redo())}
        onClick={(e) => void e.chain().focus().redo().run()}
      >
        <Redo2 {...icon} />
      </ToolButton>
      <Divider />
      <ToolButton
        editor={editor}
        title="Đoạn văn"
        active={(e) => e.isActive("paragraph")}
        onClick={(e) => void e.chain().focus().setParagraph().run()}
      >
        <span className="px-1 text-small font-semibold">¶</span>
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Tiêu đề 2"
        active={(e) => e.isActive("heading", { level: 2 })}
        onClick={(e) => void e.chain().focus().toggleHeading({ level: 2 }).run()}
      >
        <span className="px-1 text-small font-bold">H2</span>
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Tiêu đề 3"
        active={(e) => e.isActive("heading", { level: 3 })}
        onClick={(e) => void e.chain().focus().toggleHeading({ level: 3 }).run()}
      >
        <span className="px-1 text-small font-bold">H3</span>
      </ToolButton>
      <Divider />
      <ToolButton
        editor={editor}
        title="Đậm"
        active={(e) => e.isActive("bold")}
        onClick={(e) => void e.chain().focus().toggleBold().run()}
      >
        <Bold {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Nghiêng"
        active={(e) => e.isActive("italic")}
        onClick={(e) => void e.chain().focus().toggleItalic().run()}
      >
        <Italic {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Gạch chân"
        active={(e) => e.isActive("underline")}
        onClick={(e) => void e.chain().focus().toggleUnderline().run()}
      >
        <UnderlineIcon {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Gạch ngang"
        active={(e) => e.isActive("strike")}
        onClick={(e) => void e.chain().focus().toggleStrike().run()}
      >
        <Strikethrough {...icon} />
      </ToolButton>
      <Divider />
      <ToolButton
        editor={editor}
        title="Căn trái"
        active={(e) => e.isActive({ textAlign: "left" })}
        onClick={(e) => void e.chain().focus().setTextAlign("left").run()}
      >
        <AlignLeft {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Căn giữa"
        active={(e) => e.isActive({ textAlign: "center" })}
        onClick={(e) => void e.chain().focus().setTextAlign("center").run()}
      >
        <AlignCenter {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Căn phải"
        active={(e) => e.isActive({ textAlign: "right" })}
        onClick={(e) => void e.chain().focus().setTextAlign("right").run()}
      >
        <AlignRight {...icon} />
      </ToolButton>
      <Divider />
      <ToolButton
        editor={editor}
        title="Danh sách"
        active={(e) => e.isActive("bulletList")}
        onClick={(e) => void e.chain().focus().toggleBulletList().run()}
      >
        <List {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Danh sách số"
        active={(e) => e.isActive("orderedList")}
        onClick={(e) => void e.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Trích dẫn"
        active={(e) => e.isActive("blockquote")}
        onClick={(e) => void e.chain().focus().toggleBlockquote().run()}
      >
        <Quote {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Khối mã"
        active={(e) => e.isActive("codeBlock")}
        onClick={(e) => void e.chain().focus().toggleCodeBlock().run()}
      >
        <CodeXml {...icon} />
      </ToolButton>
      <ToolButton
        editor={editor}
        title="Đường kẻ ngang"
        onClick={(e) => void e.chain().focus().setHorizontalRule().run()}
      >
        <Minus {...icon} />
      </ToolButton>
      <Divider />
      <button
        type="button"
        title="Chèn ảnh (tải lên)"
        aria-label="Chèn ảnh (tải lên)"
        className="rounded p-1.5 text-ink-muted hover:bg-recess"
        onMouseDown={(e) => e.preventDefault()}
        onClick={onImageClick}
      >
        <ImagePlus {...icon} />
      </button>
      <ToolButton
        editor={editor}
        title="Chèn bảng 3×3"
        onClick={(e) =>
          void e.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
        }
      >
        <Table {...icon} />
      </ToolButton>
      {inTable && (
        <>
          <ToolButton
            editor={editor}
            title="Thêm hàng"
            onClick={(e) => void e.chain().focus().addRowAfter().run()}
          >
            <span className="px-1 text-label font-semibold">+Hàng</span>
          </ToolButton>
          <ToolButton
            editor={editor}
            title="Xóa hàng"
            onClick={(e) => void e.chain().focus().deleteRow().run()}
          >
            <span className="px-1 text-label font-semibold">−Hàng</span>
          </ToolButton>
          <ToolButton
            editor={editor}
            title="Thêm cột"
            onClick={(e) => void e.chain().focus().addColumnAfter().run()}
          >
            <span className="px-1 text-label font-semibold">+Cột</span>
          </ToolButton>
          <ToolButton
            editor={editor}
            title="Xóa cột"
            onClick={(e) => void e.chain().focus().deleteColumn().run()}
          >
            <span className="px-1 text-label font-semibold">−Cột</span>
          </ToolButton>
          <ToolButton
            editor={editor}
            title="Xóa bảng"
            onClick={(e) => void e.chain().focus().deleteTable().run()}
          >
            <span className="px-1 text-label font-semibold">Xóa bảng</span>
          </ToolButton>
        </>
      )}
      <ToolButton
        editor={editor}
        title="Xóa định dạng"
        onClick={(e) => void e.chain().focus().unsetAllMarks().clearNodes().run()}
      >
        <RemoveFormatting {...icon} />
      </ToolButton>
      <Divider />
      <div className="flex items-center gap-1">
        <input
          value={linkUrl}
          onChange={(e) => setLinkUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              applyLink();
            }
          }}
          placeholder={
            linkActive ? "Sửa link — Enter để gán, trống để gỡ" : "Dán URL rồi Enter để gán link"
          }
          className="w-44 rounded border border-rule bg-ground px-1.5 py-1 text-label"
          aria-label="URL của link"
        />
        <ToolButton
          editor={editor}
          title="Gán link"
          active={(e) => e.isActive("link")}
          onClick={() => applyLink()}
        >
          <Link2 {...icon} />
        </ToolButton>
        {linkActive && (
          <ToolButton
            editor={editor}
            title="Gỡ link"
            onClick={(e) => void e.chain().focus().unsetLink().run()}
          >
            <Link2Off {...icon} />
          </ToolButton>
        )}
      </div>
      {imageActive && (
        <div className="flex items-center gap-1">
          <input
            value={imgAlt}
            onChange={(e) => setImgAlt(e.target.value)}
            placeholder="Chữ thay thế (alt)"
            className="w-32 rounded border border-rule bg-ground px-1.5 py-1 text-label"
            aria-label="Chữ thay thế của ảnh"
          />
          <input
            value={imgCaption}
            onChange={(e) => setImgCaption(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                applyImageMeta();
              }
            }}
            placeholder="Chú thích (caption)"
            className="w-36 rounded border border-rule bg-ground px-1.5 py-1 text-label"
            aria-label="Chú thích của ảnh"
          />
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={applyImageMeta}
            className="rounded bg-recess px-2 py-1 text-label font-semibold hover:bg-rule"
          >
            Gán
          </button>
        </div>
      )}
    </div>
  );
}

function Divider() {
  return <span className="mx-0.5 h-5 w-px bg-rule" aria-hidden />;
}
