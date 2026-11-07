const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST() {
  const upstream = await fetch(`${API_BASE}/admin/recompute`, {
    method: "POST",
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
