// BFF: generate (POST) / fetch latest (GET) internal macro intelligence report
// (admin-gated).
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token");
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }
  const upstream = await fetch(`${API_BASE}/reports/internal/latest`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request) {
  const { token } = (await req.json().catch(() => ({}))) as { token?: string };
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/reports/internal`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
