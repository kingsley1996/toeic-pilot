"use client";

import { useParams } from "next/navigation";

import { LessonForm } from "../../lesson-form";

/** Sửa bài học — cùng `LessonForm` với trang tạo, khác ở chỗ có `lessonId`. */
export default function EditGrammarLessonPage() {
  const { lessonId } = useParams();
  return <LessonForm lessonId={String(lessonId)} topicId={null} />;
}
