const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const { sessionId, slotKey, sentToEmail, askedQuestion } = (await req.json().catch(() => ({}))) as {
    sessionId?: string;
    slotKey?: string;
    sentToEmail?: string;
    askedQuestion?: string;
  };
  if (!sessionId || !sentToEmail) {
    return Response.json({ detail: "missing sessionId or sentToEmail" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/sessions/${sessionId}/relays`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    // slot_key omitted -> the API resolves the session's current question
    body: JSON.stringify({
      slot_key: slotKey ?? null,
      sent_to_email: sentToEmail,
      asked_question: askedQuestion ?? null,
    }),
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
