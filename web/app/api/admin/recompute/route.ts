const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const { token } = (await req.json().catch(() => ({}))) as { token?: string };
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/admin/recompute`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
