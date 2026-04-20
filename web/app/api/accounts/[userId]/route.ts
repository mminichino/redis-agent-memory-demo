import { NextResponse } from "next/server";
import { getEnv } from "@/lib/env";
import { getCurrentUser } from "@/lib/auth";
import { deleteAccount } from "@/lib/redis";

export async function DELETE(
  _request: Request,
  context: { params: { userId: string } }
) {
  const user = await getCurrentUser();
  if (!user || !user.is_admin) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 403 });
  }

  const userId = context.params.userId;
  if (userId === getEnv().adminUser) {
    return NextResponse.json({ error: "Admin account cannot be removed." }, { status: 400 });
  }

  await deleteAccount(userId);
  return NextResponse.json({ ok: true });
}
