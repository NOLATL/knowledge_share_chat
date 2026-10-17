const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get("sessionId");
  if (!sessionId) {
    return new Response("missing sessionId", { status: 400 });
  }

  const res = await fetch(`${API_BASE}/sessions/${sessionId}/documents`);
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request) {
  const form = await req.formData();
  const sessionId = form.get("sessionId");
  const file = form.get("file");
  const docType = form.get("doc_type");

  if (typeof sessionId !== "string" || !sessionId || !(file instanceof File)) {
    return new Response("missing sessionId or file", { status: 400 });
  }

  const upstream = new FormData();
  upstream.set("file", file);
  if (typeof docType === "string" && docType) {
    upstream.set("doc_type", docType);
  }

  const res = await fetch(`${API_BASE}/sessions/${sessionId}/documents`, {
    method: "POST",
    body: upstream,
  });
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
