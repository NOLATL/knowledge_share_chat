// BFF: generate (POST) / fetch latest (GET) internal macro intelligence report.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET() {
  const upstream = await fetch(`${API_BASE}/reports/internal/latest`, {
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST() {
  const upstream = await fetch(`${API_BASE}/reports/internal`, {
    method: "POST",
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
