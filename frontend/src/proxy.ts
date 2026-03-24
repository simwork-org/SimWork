import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  if (!req.auth) {
    const homeUrl = new URL("/", req.url);
    return NextResponse.redirect(homeUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!landing|login|invite|api/auth|_next/static|_next/image|favicon.ico).+)"],
};
