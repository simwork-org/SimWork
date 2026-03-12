import { CompletionScreen } from "@/components/completion-screen";

export default async function CompletionPage({
  params
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <CompletionScreen sessionId={sessionId} />;
}
