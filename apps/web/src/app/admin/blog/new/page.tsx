"use client";

import { BlogPostForm } from "../post-form";

/** Viết bài mới — cùng `BlogPostForm` với trang sửa, khác ở chỗ chưa có `postId`. */
export default function NewBlogPostPage() {
  return <BlogPostForm postId={null} />;
}
