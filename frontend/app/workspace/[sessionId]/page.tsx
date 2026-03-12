import { WorkspaceScreen } from "@/components/workspace-screen";

export default async function WorkspacePage({
  params
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <WorkspaceScreen sessionId={sessionId} />;
}
