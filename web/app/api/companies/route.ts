// BFF: company directory for the external-deliverable picker.
const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const includeSynthetic = new URL(req.url).searchParams.get("includeSynthetic") === "true";
  const res = await fetch(`${API_BASE}/companies?include_synthetic=${includeSynthetic}`);
  return new Response(await res.text(), {
    status: res.status,
    headers: { "content-type": "application/json" },
  });
}
