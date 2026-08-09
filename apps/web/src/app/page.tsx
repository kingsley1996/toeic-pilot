"use client";

import { ButtonLink, Card, Page, Skeleton } from "@/components/ui";
import { useSession } from "@/lib/session";

const FEATURES = [
  {
    icon: "🎧",
    title: "Dictation",
    body: "Nghe và gõ lại. Chấm theo từng từ, chỉ ra chính xác chỗ nghe sót.",
  },
  {
    icon: "🗣️",
    title: "Từ vựng 4 giọng",
    body: "Mỗi từ được đọc bằng giọng Mỹ, Anh, Úc và Canada — đúng bốn accent TOEIC dùng.",
  },
  {
    icon: "🔁",
    title: "Lặp lại ngắt quãng",
    body: "Thuật toán SM-2 quyết định hôm nay ôn từ nào, dựa trên chính lần bạn trả lời trước.",
  },
];

export default function HomePage() {
  const { status } = useSession();

  return (
    <Page className="max-w-4xl">
      <section className="py-8 text-center sm:py-16">
        <h1 className="mx-auto max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Học tiếng Anh mỗi ngày,
          <span className="text-brand"> luyện TOEIC có phương pháp</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-text-muted">
          Từ vựng theo chủ đề với phát âm bốn giọng, bài nghe chép chính tả được chấm từng từ, và
          lịch ôn tập tự điều chỉnh theo trí nhớ của bạn.
        </p>

        {/* Three states, not two. Treating "loading" as signed-out would show a
            returning learner "Bắt đầu miễn phí" for a beat before swapping it for
            "Vào học" — the same wrong-state flash the header used to have, just
            further down the page. */}
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {status === "loading" && (
            <>
              <Skeleton className="h-12 w-44" />
              <Skeleton className="h-12 w-44" />
            </>
          )}
          {status === "authenticated" && (
            <>
              <ButtonLink href="/learn" size="lg">
                Vào học
              </ButtonLink>
              <ButtonLink href="/dashboard" variant="secondary" size="lg">
                Bảng điều khiển
              </ButtonLink>
            </>
          )}
          {status === "anonymous" && (
            <>
              <ButtonLink href="/register" size="lg">
                Bắt đầu miễn phí
              </ButtonLink>
              <ButtonLink href="/login" variant="secondary" size="lg">
                Tôi đã có tài khoản
              </ButtonLink>
            </>
          )}
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {FEATURES.map((feature) => (
          <Card key={feature.title} className="p-5">
            <div aria-hidden className="text-2xl">
              {feature.icon}
            </div>
            <h2 className="mt-3 font-semibold">{feature.title}</h2>
            <p className="mt-1.5 text-sm text-text-muted">{feature.body}</p>
          </Card>
        ))}
      </section>
    </Page>
  );
}
