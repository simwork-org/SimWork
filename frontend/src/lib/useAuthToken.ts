"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { setAuthToken } from "@/lib/api";

export function useAuthToken() {
  const { data: session } = useSession();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = (session as Record<string, unknown> | null)?.id_token as string | undefined;
    setAuthToken(token ?? null);
    setReady(!!session && !!token);
  }, [session]);

  return ready ? session : null;
}
