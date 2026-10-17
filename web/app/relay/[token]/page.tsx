import RelayAnswerForm from "@/components/RelayAnswerForm";

export default async function RelayPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <RelayAnswerForm token={token} />;
}
