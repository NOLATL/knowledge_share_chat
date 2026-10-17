// BFF: resume a session by magic-link token.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token");
  if (!token) {
    return new Response("missing token", { status: 400 });
  }
  const res = await fetch(`${API_BASE}/sessions/by-token/${token}`);
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
