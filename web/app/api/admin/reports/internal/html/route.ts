// BFF: view the latest internal macro intelligence report as a styled page.
import { renderStandaloneHtml } from "@/lib/markdown";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token");
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/reports/internal/latest`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!upstream.ok) {
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  }
  const report = (await upstream.json()) as { rendered_md: string; created_at: string };
  const html = renderStandaloneHtml(
    "Internal Intelligence — Cohort View",
    report.rendered_md,
    `Internal only · Generated ${new Date(report.created_at).toLocaleString("en-US")}`,
  );
  return new Response(html, {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
