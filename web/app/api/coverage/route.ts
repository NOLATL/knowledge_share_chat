// BFF: proxy slot-coverage for the progress indicator.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const sessionId = new URL(req.url).searchParams.get("sessionId");
  if (!sessionId) {
    return new Response("missing sessionId", { status: 400 });
  }
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/coverage`);
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
