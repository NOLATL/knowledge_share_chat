// BFF: create a discovery session by proxying to the FastAPI service.
// Forwards an optional company-intake body from the pre-chat form.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const body = await req.text().catch(() => "");
  const res = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body || "{}",
  });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
