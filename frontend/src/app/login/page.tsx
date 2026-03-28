import { redirect } from "next/navigation";
import { buildLandingAuthUrl, type AuthIntent } from "@/lib/auth-routing";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const role = Array.isArray(params.role) ? params.role[0] : params.role;
  const invite = Array.isArray(params.invite) ? params.invite[0] : params.invite;
  const next = Array.isArray(params.next) ? params.next[0] : params.next;
  const auth: AuthIntent = role === "company" ? "company" : "candidate";

  redirect(buildLandingAuthUrl({ auth, next, invite }));
}
