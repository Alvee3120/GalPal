import { cookies } from "next/headers";

// Tells the Navbar whether a session exists. The refresh token outlives the 15-minute access token,
// so its presence is what marks the user as logged in.
export async function GET() {
  const store = await cookies();
  return Response.json(
    { authenticated: store.has("refresh_token") },
    { headers: { "Cache-Control": "no-store" } },
  );
}
