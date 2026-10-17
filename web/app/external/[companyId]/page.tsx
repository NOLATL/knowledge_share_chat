import ExternalCompanyView from "@/components/ExternalCompanyView";

type PageProps = { params: Promise<{ companyId: string }> };

export default async function ExternalCompanyPage({ params }: PageProps) {
  const { companyId } = await params;
  return <ExternalCompanyView companyId={companyId} />;
}
