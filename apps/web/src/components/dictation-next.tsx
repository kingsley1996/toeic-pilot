"use client";

import {
  API_ROUTES,
  type DictationSectionDetail,
  type DictationTopicDetail,
  type DictationTopicPublic,
} from "@toeic-pilot/shared";
import { ArrowRight, PartyPopper } from "lucide-react";
import { useEffect, useState } from "react";

import { ButtonLink, Panel, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";

/**
 * "Xong bài này rồi thì đi đâu tiếp?"
 *
 * Nội dung dictation là một cái cây bốn tầng, và cho tới giờ nó chỉ đi được
 * theo chiều XUỐNG: học viên gõ xong câu cuối của một bài rồi ngồi đó, vì lối ra
 * duy nhất là bấm breadcrumb ngược lên hai tầng rồi tự tìm bài kế. Ai cũng làm
 * được, nhưng nó bắt người vừa học xong phải tự điều hướng — đúng cái việc lẽ ra
 * hệ thống làm hộ.
 *
 * Đi lên từng tầng một, và **chỉ lên khi tầng dưới đã hết**:
 *
 *   còn bài chưa xong trong unit  ->  bài đó
 *   xong cả unit                  ->  unit kế tiếp trong chủ đề
 *   xong cả chủ đề                ->  chủ đề kế tiếp
 *   hết                           ->  nói thẳng là đã hết
 *
 * Ba lượt gọi, và chúng chỉ chạy khi bài đã xong — đây không phải thứ nạp kèm
 * mọi lần mở trang. Mỗi tầng chỉ hỏi khi tầng dưới nó trả lời "hết rồi", nên
 * trường hợp thường gặp nhất (còn bài trong unit) tốn đúng một lượt.
 *
 * Chọn unit kế tiếp **theo thứ tự**, không phải "unit chưa xong gần nhất".
 * Muốn biết unit nào chưa xong thì phải hỏi tiến độ của từng unit một, tức là
 * mỗi unit một lượt gọi; và một cái nút nhảy cóc qua unit 3 để tới unit 5 cũng
 * khó đoán hơn là một cái nút đi tiếp đúng một bậc.
 */

type Destination = {
  href: string;
  /** Nhãn của TẦNG, để người học biết mình vừa qua một cột mốc cỡ nào. */
  kind: string;
  name: string;
};

async function findNext(
  token: string,
  topicId: string,
  sectionId: string,
  storyId: string,
): Promise<Destination | null> {
  const section = await apiFetch<DictationSectionDetail>(API_ROUTES.dictationSection(sectionId), {
    token,
  });
  const unfinished = section.stories.find(
    (story) => story.id !== storyId && story.progress.completed_items < story.progress.total_items,
  );
  if (unfinished) {
    return {
      href: `/learn/dictation/stories/${unfinished.id}`,
      kind: "Bài tiếp theo",
      name: unfinished.title,
    };
  }

  const topic = await apiFetch<DictationTopicDetail>(API_ROUTES.dictationTopic(topicId), {
    token,
  });
  const at = topic.sections.findIndex((s) => s.id === sectionId);
  const nextSection = at >= 0 ? topic.sections[at + 1] : undefined;
  if (nextSection) {
    return {
      href: `/learn/dictation/sections/${nextSection.id}`,
      kind: "Unit tiếp theo",
      name: nextSection.name,
    };
  }

  const topics = await apiFetch<DictationTopicPublic[]>(API_ROUTES.dictationTopics, { token });
  const topicAt = topics.findIndex((t) => t.id === topicId);
  const nextTopic = topicAt >= 0 ? topics[topicAt + 1] : undefined;
  if (nextTopic) {
    return {
      href: `/learn/dictation/topics/${nextTopic.id}`,
      kind: "Chủ đề tiếp theo",
      name: nextTopic.name,
    };
  }
  return null;
}

export function DictationNextUp({
  token,
  topicId,
  sectionId,
  storyId,
}: {
  token: string | null;
  topicId: string;
  sectionId: string;
  storyId: string;
}) {
  const [next, setNext] = useState<Destination | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    findNext(token, topicId, sectionId, storyId)
      .then((found) => {
        if (!alive) return;
        setNext(found);
        setDone(found === null);
      })
      // Hỏng thì im lặng không hiện gì. Khối này là một lối đi tắt; breadcrumb
      // phía trên vẫn đưa được người học đi bất cứ đâu, nên một thông báo lỗi ở
      // đây chỉ làm hỏng đúng khoảnh khắc vừa xong một bài.
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token, topicId, sectionId, storyId]);

  if (!token) return null;

  if (!next && !done) {
    return (
      <Panel className="mt-4 p-4" aria-busy>
        <Skeleton className="h-5 w-48" />
        <Skeleton className="mt-3 h-9 w-40" />
      </Panel>
    );
  }

  if (done) {
    return (
      <Panel className="mt-4 border-ok p-4">
        <p className="flex items-center gap-2 font-semibold text-ok">
          <PartyPopper size={16} strokeWidth={2} aria-hidden />
          <span className="text-ink">Bạn đã nghe hết nội dung hiện có.</span>
        </p>
        <p className="mt-1 text-small text-ink-muted">
          Nội dung mới vẫn đang được soạn thêm. Trong lúc chờ, nghe ngẫu nhiên là cách ôn lại tốt.
        </p>
        <div className="mt-3">
          <ButtonLink href="/learn/dictation/random" variant="secondary">
            Nghe ngẫu nhiên
          </ButtonLink>
        </div>
      </Panel>
    );
  }

  return (
    <Panel className="mt-4 border-ok p-4">
      <p className="text-label font-semibold uppercase text-ok">Xong bài này</p>
      <p className="mt-1.5 text-ink">
        <span className="text-ink-muted">{next!.kind}: </span>
        <span className="font-semibold">{next!.name}</span>
      </p>
      <div className="mt-3">
        <ButtonLink href={next!.href}>
          Đi tiếp
          <ArrowRight size={16} strokeWidth={2} aria-hidden />
        </ButtonLink>
      </div>
    </Panel>
  );
}
