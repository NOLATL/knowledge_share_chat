// BFF: the external destination's data — company profile, exec rollup,
// per-function breakdown with benchmarks + personas.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: Request, { params }: Params) {
  const { id } = await params;
  const res = await fetch(`${API_BASE}/companies/${id}/overview`, { cache: "no-store" });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
