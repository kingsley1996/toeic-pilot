// Spike TikTok Embed Player API — CHẠY TAY TRÊN TRÌNH DUYỆT THẬT, không phải CI.
// Headless bị tường bot TikTok chặn (không message nào về), nên script này mở
// Chrome headed. Chạy: `node spike-tiktok-player.mjs` (cần màn hình).
// Copy toàn bộ output gửi lại để chốt thiết kế Phase 3.
import { chromium } from "@playwright/test";

const VIDEO_ID = "7631511471259733270"; // video nói tiếng Anh, có sub, embed được

const browser = await chromium.launch({ headless: false });
const page = await browser.newPage();
const out = await page.evaluate(
  ({ videoId }) =>
    new Promise((resolve) => {
      const log = [];
      const stamp = (t0) => ((Date.now() - t0) / 1000).toFixed(1) + "s";
      const t0 = Date.now();
      const say = (s) => log.push(`${stamp(t0)} ${s}`);

      const iframe = document.createElement("iframe");
      iframe.src =
        `https://www.tiktok.com/player/v1/${videoId}` +
        `?controls=1&progress_bar=1&timestamp=1&loop=0&autoplay=0&rel=0`;
      iframe.width = "360";
      iframe.height = "640";
      document.body.append(iframe);
      const send = (type, value) =>
        iframe.contentWindow.postMessage({ type, value, "x-tiktok-player": true }, "*");

      let timeEvents = 0;
      let lastTime = null;
      window.addEventListener("message", (e) => {
        if (!e.data || e.data["x-tiktok-player"] !== true) return;
        if (e.data.type === "onCurrentTime") {
          timeEvents += 1;
          lastTime = e.data.value;
          if (timeEvents <= 3 || timeEvents % 10 === 0)
            say(`onCurrentTime n=${timeEvents} ${JSON.stringify(e.data.value)}`);
          return;
        }
        say(`${e.data.type} ${JSON.stringify(e.data.value ?? "").slice(0, 100)}`);
      });

      // oEmbed CORS từ trình duyệt thật
      fetch(`https://www.tiktok.com/oembed?url=https://www.tiktok.com/@x/video/${videoId}`)
        .then(async (r) => {
          const j = await r.json();
          say(`oEmbed ok title=${JSON.stringify((j.title || "").slice(0, 40))}`);
        })
        .catch((err) => say(`oEmbed FAIL ${String(err).slice(0, 80)}`));

      const t = setInterval(() => {
        if (!log.some((l) => l.includes("onPlayerReady"))) return;
        clearInterval(t);
        send("play");
        // S1: seek lúc paused có giữ pause không?
        setTimeout(() => {
          send("pause");
          say("CHECK paused, will seekTo(3) in 1s");
        }, 3000);
        setTimeout(() => send("seekTo", 3), 4000);
        setTimeout(
          () => say(`after-seek playing-or-paused unknown, lastTime=${JSON.stringify(lastTime)}`),
          6000,
        );
        // S2: setPlaybackRate blind (không tài liệu) — có event/lỗi gì không?
        setTimeout(() => {
          send("play");
          iframe.contentWindow.postMessage(
            { type: "setPlaybackRate", value: 0.75, "x-tiktok-player": true },
            "*",
          );
          say("sent blind setPlaybackRate(0.75)");
        }, 7000);
        setTimeout(() => {
          say(`timeEvents total=${timeEvents}`);
          resolve(log);
        }, 14000);
      }, 300);
      setTimeout(() => resolve(["TIMEOUT-NO-READY", ...log]), 30000);
    }),
  { videoId: VIDEO_ID },
);
console.log(out.join("\n"));
await browser.close();
