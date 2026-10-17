const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const search = new URL(req.url).searchParams;
  const sessionId = search.get("sessionId");
  const token = search.get("token");
  if (!sessionId) {
    return Response.json({ detail: "missing sessionId" }, { status: 400 });
  }
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/admin/demo/status?session_id=${encodeURIComponent(sessionId)}`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
