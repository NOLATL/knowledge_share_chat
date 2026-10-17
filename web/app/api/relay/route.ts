const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

function tokenFrom(req: Request) {
  return new URL(req.url).searchParams.get("token");
}

export async function GET(req: Request) {
  const token = tokenFrom(req);
  if (!token) {
    return Response.json({ detail: "missing token" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/relays/${token}`, { cache: "no-store" });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request) {
  const token = tokenFrom(req);
  if (!token) {
    return Response.json({ detail: "missing token" }, { status: 400 });
  }
  const { replyText } = (await req.json().catch(() => ({}))) as { replyText?: string };
  if (!replyText) {
    return Response.json({ detail: "missing replyText" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/relays/${token}/answer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ reply_text: replyText }),
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
