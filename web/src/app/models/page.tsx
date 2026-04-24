import { redirect } from "next/navigation";
import { APP_BASE } from "@/lib/app-path";

export default function LegacyModelsPath() {
  redirect(`${APP_BASE}/models`);
}
