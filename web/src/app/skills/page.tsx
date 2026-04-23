import { redirect } from "next/navigation";

/** Legacy route: Composio integrations live under Connections. */
export default function SkillsRedirectPage() {
  redirect("/connections");
}
