import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  if (!req.auth && req.nextUrl.pathname !== "/login") {
    const landingUrl = new URL("/landing", req.url);
    return NextResponse.redirect(landingUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!landing|login|api/auth|_next/static|_next/image|favicon.ico).*)"],
};
