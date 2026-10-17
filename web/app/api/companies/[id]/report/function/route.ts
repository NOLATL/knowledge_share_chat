// BFF: fetch/generate the function-level external deliverable (?function=...).
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

type Params = { params: Promise<{ id: string }> };

function functionKeyFrom(req: Request) {
  return new URL(req.url).searchParams.get("function");
}

export async function GET(req: Request, { params }: Params) {
  const { id } = await params;
  const functionKey = functionKeyFrom(req);
  if (!functionKey) {
    return Response.json({ detail: "missing function" }, { status: 400 });
  }
  const url = new URL(`${API_BASE}/companies/${id}/reports/function/latest`);
  url.searchParams.set("function_key", functionKey);
  const res = await fetch(url, { cache: "no-store" });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request, { params }: Params) {
  const { id } = await params;
  const functionKey = functionKeyFrom(req);
  if (!functionKey) {
    return Response.json({ detail: "missing function" }, { status: 400 });
  }
  const url = new URL(`${API_BASE}/companies/${id}/reports/function`);
  url.searchParams.set("function_key", functionKey);
  const res = await fetch(url, { method: "POST" });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
