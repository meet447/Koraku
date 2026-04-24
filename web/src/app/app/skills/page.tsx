import { redirect } from "next/navigation";
import { APP_BASE } from "@/lib/app-path";

/** Legacy route: Composio integrations live under Connections. */
export default function SkillsRedirectPage() {
  redirect(`${APP_BASE}/connections`);
}
