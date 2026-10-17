// BFF: bridge useChat's text-stream transport to the FastAPI streaming endpoint.
// The api emits SSE (`data: {"type":"text-delta","delta":"..."}` ... `{"type":"done"}`);
// we translate it to the raw plain-text chunks the text-stream protocol expects.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const { sessionId, message } = await req.json();
  if (!sessionId || typeof message !== "string") {
    return new Response("missing sessionId or message", { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!upstream.ok || !upstream.body) {
    return new Response("upstream error", { status: 502 });
  }

  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let buffer = "";
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let sep: number;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const event = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            const dataLine = event.split("\n").find((l) => l.startsWith("data:"));
            if (!dataLine) continue;
            try {
              const obj = JSON.parse(dataLine.slice(dataLine.indexOf(":") + 1).trim());
              if (obj.type === "text-delta" && obj.delta) {
                controller.enqueue(encoder.encode(obj.delta));
              }
            } catch {
              // ignore malformed event lines
            }
          }
        }
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
