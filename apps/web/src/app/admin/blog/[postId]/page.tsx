"use client";

import { useParams } from "next/navigation";

import { BlogPostForm } from "../post-form";

/** Sửa bài — cùng `BlogPostForm` với trang tạo, khác ở chỗ có `postId`. */
export default function EditBlogPostPage() {
  const { postId } = useParams();
  return <BlogPostForm postId={String(postId)} />;
}
