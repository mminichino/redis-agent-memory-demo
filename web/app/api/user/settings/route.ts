import { NextResponse } from "next/server";
import { z } from "zod";
import { getCurrentUser } from "@/lib/auth";
import { updateUserSettings } from "@/lib/redis";
import type { UserSettings } from "@/lib/types";

const patchSchema = z.object({
  show_tool_responses: z.boolean().optional()
});

export async function GET() {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }
  return NextResponse.json({ settings: user.settings });
}

export async function PATCH(request: Request) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }
  const body = await request.json().catch(() => null);
  const parsed = patchSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid settings payload." }, { status: 400 });
  }
  const partial: Partial<UserSettings> = {};
  if (typeof parsed.data.show_tool_responses === "boolean") {
    partial.show_tool_responses = parsed.data.show_tool_responses;
  }
  if (Object.keys(partial).length === 0) {
    return NextResponse.json({ settings: user.settings });
  }
  const settings = await updateUserSettings(user.user_id, partial);
  return NextResponse.json({ settings });
}
