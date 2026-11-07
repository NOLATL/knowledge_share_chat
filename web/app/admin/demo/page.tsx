import DemoCockpit from "@/components/DemoCockpit";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AdminDemoPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const sessionParam = params?.sessionId;
  const sessionId = Array.isArray(sessionParam) ? sessionParam[0] : sessionParam;

  return <DemoCockpit initialSessionId={sessionId ?? ""} />;
}
