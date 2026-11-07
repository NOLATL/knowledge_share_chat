// BFF: the internal destination's cohort snapshot.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET() {
  const upstream = await fetch(`${API_BASE}/admin/internal`, {
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
