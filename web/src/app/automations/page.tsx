import { redirect } from "next/navigation";
import { APP_BASE } from "@/lib/app-path";

export default function LegacyAutomationsPath() {
  redirect(`${APP_BASE}/automations`);
}
