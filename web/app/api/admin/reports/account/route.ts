// BFF: fetch/generate the internal account intel report (?companyId=).
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

function paramsFrom(req: Request) {
  const search = new URL(req.url).searchParams;
  return { companyId: search.get("companyId") };
}

function missing(companyId: string | null) {
  if (!companyId) return Response.json({ detail: "missing companyId" }, { status: 400 });
  return null;
}

export async function GET(req: Request) {
  const { companyId } = paramsFrom(req);
  const bad = missing(companyId);
  if (bad) return bad;
  const upstream = await fetch(`${API_BASE}/companies/${companyId}/reports/account/latest`, {
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request) {
  const { companyId } = paramsFrom(req);
  const bad = missing(companyId);
  if (bad) return bad;
  const upstream = await fetch(`${API_BASE}/companies/${companyId}/reports/account`, {
    method: "POST",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
