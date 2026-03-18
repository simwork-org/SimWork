"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { InviteValidation } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const [invite, setInvite] = useState<InviteValidation | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/v1/invite/${token}`)
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "Invalid invite link");
        }
        return res.json();
      })
      .then((data) => setInvite(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  const handleSignIn = () => {
    document.cookie = `simwork_invite=${token};path=/;max-age=600`;
    signIn("google", { callbackUrl: "/auth/redirect" });
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{
        backgroundColor: "#101122",
        backgroundImage: [
          "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)",
          "radial-gradient(circle at 25% 50%, rgba(16,185,129,0.15) 0%, transparent 50%)",
          "radial-gradient(circle at 80% 15%, rgba(99,102,241,0.12) 0%, transparent 40%)",
        ].join(", "),
        backgroundSize: "24px 24px, 100% 100%, 100% 100%",
      }}
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-10 text-center">
        <div className="flex items-center justify-center size-14 bg-[#10B981] rounded-2xl text-white mx-auto mb-6">
          <span className="material-symbols-outlined text-3xl">strategy</span>
        </div>

        {loading && (
          <p className="text-slate-400 text-sm animate-pulse">Loading assessment details...</p>
        )}

        {error && (
          <>
            <h2 className="text-xl font-bold text-white mb-2">Invalid Invite</h2>
            <p className="text-sm text-slate-400">{error}</p>
          </>
        )}

        {invite && (
          <>
            <h2 className="text-2xl font-bold text-white mb-2">
              You&apos;re Invited to an Assessment
            </h2>
            {invite.company_name && (
              <p className="text-sm text-slate-400 mb-1">
                From <span className="text-white font-medium">{invite.company_name}</span>
              </p>
            )}
            {invite.assessment_title && (
              <p className="text-sm text-[#10B981] font-medium mb-6">{invite.assessment_title}</p>
            )}
            {!invite.assessment_title && <div className="mb-6" />}

            <p className="text-sm text-slate-400 mb-8 leading-relaxed">
              You&apos;ll be placed in a realistic business simulation where you investigate a
              problem, collaborate with AI teammates, and deliver your recommendations — all
              in about 30 minutes.
            </p>

            <button
              onClick={handleSignIn}
              className="w-full rounded-xl px-8 py-4 bg-[#10B981] text-base font-bold text-white shadow-lg shadow-[#10B981]/25 hover:shadow-[#10B981]/40 transition-shadow"
            >
              Sign in with Google to Begin
            </button>

            <p className="text-xs text-slate-500 mt-4">
              Powered by SimWork
            </p>
          </>
        )}
      </div>
    </div>
  );
}
