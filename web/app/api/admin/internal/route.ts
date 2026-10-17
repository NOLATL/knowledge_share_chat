// BFF: the internal destination's cohort snapshot (admin-gated).
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token");
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }
  const upstream = await fetch(`${API_BASE}/admin/internal`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
