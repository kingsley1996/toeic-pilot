"use client";

import { useParams } from "next/navigation";

import { LessonForm } from "../../../lesson-form";

/** Bài mới trong chủ đề `topicId` — slug nằm ở route thay vì query để trang
    dựng được không cần Suspense quanh `useSearchParams`. */
export default function NewGrammarLessonPage() {
  const { topicId } = useParams();
  return <LessonForm lessonId={null} topicId={String(topicId)} />;
}
