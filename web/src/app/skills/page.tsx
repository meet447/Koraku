import { redirect } from "next/navigation";
import { APP_BASE } from "@/lib/app-path";

/** Old path; skills UI merged into Connections under the authenticated app. */
export default function LegacySkillsRedirect() {
  redirect(`${APP_BASE}/connections`);
}
