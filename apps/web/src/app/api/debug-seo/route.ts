import { NextResponse } from "next/server";

/* DEBUG TẠM cho GĐ3 SEO — xóa sau khi biết vì sao fetch từ Vercel tới API hỏng. */
export async function GET() {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const out: Record<string, unknown> = { base };
  try {
    const t0 = Date.now();
    const res = await fetch(`${base}/api/v1/vocabulary?topic=positions&limit=2`);
    out.list = { status: res.status, ms: Date.now() - t0 };
  } catch (e) {
    out.list = { error: e instanceof Error ? `${e.name}: ${e.message}` : String(e) };
  }
  return NextResponse.json(out);
}
