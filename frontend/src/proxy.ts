import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";
import { buildLandingAuthUrl, inferCompanyIntent } from "@/lib/auth-routing";

export default auth((req) => {
  if (!req.auth) {
    const nextPath = `${req.nextUrl.pathname}${req.nextUrl.search}`;
    const landingUrl = new URL(
      buildLandingAuthUrl({
        auth: inferCompanyIntent(nextPath) ? "company" : "candidate",
        next: nextPath,
      }),
      req.url
    );
    return NextResponse.redirect(landingUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!landing|login|invite|api/auth|_next/static|_next/image|favicon.ico).+)"],
};
