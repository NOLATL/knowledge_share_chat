// BFF: fetch/generate the internal account intel report (?companyId=&token=).
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

function paramsFrom(req: Request) {
  const search = new URL(req.url).searchParams;
  return { companyId: search.get("companyId"), token: search.get("token") };
}

function missing(companyId: string | null, token: string | null) {
  if (!companyId) return Response.json({ detail: "missing companyId" }, { status: 400 });
  if (!token) return Response.json({ detail: "missing admin token" }, { status: 400 });
  return null;
}

export async function GET(req: Request) {
  const { companyId, token } = paramsFrom(req);
  const bad = missing(companyId, token);
  if (bad) return bad;
  const upstream = await fetch(`${API_BASE}/companies/${companyId}/reports/account/latest`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request) {
  const { companyId, token } = paramsFrom(req);
  const bad = missing(companyId, token);
  if (bad) return bad;
  const upstream = await fetch(`${API_BASE}/companies/${companyId}/reports/account`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
