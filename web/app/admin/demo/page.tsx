import DemoCockpit from "@/components/DemoCockpit";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AdminDemoPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const tokenParam = params?.token;
  const sessionParam = params?.sessionId;
  const token = Array.isArray(tokenParam) ? tokenParam[0] : tokenParam;
  const sessionId = Array.isArray(sessionParam) ? sessionParam[0] : sessionParam;

  return <DemoCockpit initialToken={token ?? ""} initialSessionId={sessionId ?? ""} />;
}
