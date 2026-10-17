// BFF: fetch/generate the external company deliverable.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: Request, { params }: Params) {
  const { id } = await params;
  const res = await fetch(`${API_BASE}/companies/${id}/reports/external/latest`);
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(_req: Request, { params }: Params) {
  const { id } = await params;
  const res = await fetch(`${API_BASE}/companies/${id}/reports/external`, { method: "POST" });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
