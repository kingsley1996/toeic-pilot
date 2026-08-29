/**
 * Điều đáng nói về từng mảnh của production (ADR-014).
 *
 * Cố ý là dữ liệu tĩnh, không phải thứ API trả về: đây là các quyết định và
 * hạn mức của gói dịch vụ, chúng thay đổi khi có người đổi nhà cung cấp chứ
 * không thay đổi theo từng phút. Số liệu sống thì đã nằm trên node rồi.
 */

export type NodeFacts = {
  title: string;
  role: string;
  facts: Array<[string, string]>;
  /** Mất node này thì người học mất gì. Trống nghĩa là không mất gì. */
  ifItFails: string;
};

export const NODE_FACTS: Record<string, NodeFacts> = {
  browser: {
    title: "Learner's browser",
    role: "Loads the page from Vercel, then talks to three different origins on its own: the API for data, and the two media stores directly.",
    facts: [
      ["Fetches media from", "the CDN, never the API"],
      ["Session token", "localStorage, revoked server-side on logout"],
    ],
    ifItFails: "",
  },
  web: {
    title: "Web · Next.js on Vercel",
    role: "Serves the pages. It never touches the database — every piece of data on screen was fetched by the browser from the API afterwards.",
    facts: [
      ["Plan", "Hobby — free, non-commercial only"],
      ["Build", "vercel-build → turbo, so the shared contract compiles first"],
      ["API address", "baked in at build time (NEXT_PUBLIC_API_URL)"],
    ],
    ifItFails: "Nobody can open the app. Already-loaded tabs keep working until reloaded.",
  },
  api: {
    title: "API · FastAPI on Render",
    role: "Every read and write except media. Runs the pre-built image CI booted, so what serves traffic is the artefact that was actually tested.",
    facts: [
      ["Instance", "Free — 512 MB, 0.1 CPU, Singapore"],
      ["Sleeps", "after 15 minutes idle, ~50 s to wake"],
      ["Hour budget", "750/month against 744 in a 31-day month"],
      ["Migrations", "alembic upgrade head runs before uvicorn binds"],
    ],
    ifItFails:
      "The app loads but stays empty. Audio and images still play, because they never came through here.",
  },
  db: {
    title: "PostgreSQL · Supabase",
    role: "Every domain table plus the migration history. Reached through the session pooler, not a direct connection.",
    facts: [
      ["Region", "ap-southeast-1 · Render is in the same region"],
      ["Port 5432", "session pooler — NOT the transaction pooler on 6543"],
      ["Why", "6543 drops prepared statements, which psycopg turns on by itself"],
      ["Free plan", "500 MB, and the project pauses after 7 days with no requests"],
    ],
    ifItFails: "Everything stops. /ready turns 503 so the uptime monitor alerts.",
  },
  redis: {
    title: "Redis · Upstash",
    role: "Token revocation list, rate limits, and the OAuth state that proves a callback belongs to a real click.",
    facts: [
      ["Region", "ap-southeast-1, same as the API"],
      ["Free plan", "500 000 commands/month"],
      ["Cost per request", "one EXISTS on every authenticated call"],
    ],
    ifItFails:
      "A soft failure, and that is the danger: logout silently stops revoking tokens and rate limits stop applying, while the site looks fine. Sign-in with Google is the exception — its state check fails closed, so it breaks loudly.",
  },
  audio: {
    title: "Audio store · Supabase Storage",
    role: "Every recording, served straight to the browser over a public bucket. The API only ever builds the URL string.",
    facts: [
      ["Objects", "3 992 clips, 94 MB"],
      ["Range requests", "supported — that is what lets a learner scrub a clip"],
      ["Uploaded by", "push_media from the authoring machine, never at request time"],
      ["Free plan", "1 GB stored, 5 GB egress/month"],
    ],
    ifItFails: "Listening exercises go silent. Everything else keeps working.",
  },
  image: {
    title: "Image store · Cloudinary",
    role: "Part 1 photographs and Part 3/4 graphics, also fetched directly by the browser.",
    facts: [
      ["Free plan", "25 GB"],
      ["Path", "res.cloudinary.com/<cloud>/image/upload/<folder>/<key>"],
      ["Provenance", "licence and attribution are NOT NULL on every row"],
    ],
    ifItFails: "Part 1 questions lose their photograph, which makes them unanswerable.",
  },
  ci: {
    title: "GitHub Actions",
    role: "Builds the API image and starts it, then publishes the very image that answered HTTP. Five jobs must pass first.",
    facts: [
      ["Publishes", "only on push to main, after the boot check"],
      ["Tags", "main for Render to follow, plus the commit sha"],
      ["Never", "points at the real database — CI runs its own Postgres"],
    ],
    ifItFails: "Nothing in production changes. Deploys simply stop.",
  },
  ghcr: {
    title: "GHCR · container registry",
    role: "Holds the published API image. Render pulls from here rather than building, so production runs a tested artefact.",
    facts: [
      ["Visibility", "public, so Render needs no registry credential"],
      ["Auto-deploy", "NO — an image-backed service ignores a new tag"],
      ["Therefore", "CI must call the Render deploy hook as its last step"],
    ],
    ifItFails:
      "The quietest failure here. Without the deploy hook, CI stays green, the new image lands in the registry, and production keeps serving the old one with nothing to report it.",
  },
};
