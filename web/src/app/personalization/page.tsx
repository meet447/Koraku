import { redirect } from "next/navigation";
import { APP_BASE } from "@/lib/app-path";

export default function LegacyPersonalizationPath() {
  redirect(`${APP_BASE}/personalization`);
}
