"use client";

import {
  CheckCircle2,
  FileText,
  FolderKanban,
  KeyRound,
  Route,
} from "lucide-react";
import clsx from "clsx";
import type { StudioPlan } from "@/lib/korakuReducer";

const ROLE_TONE: Record<string, string> = {
  Director: "border-neutral-300 bg-neutral-50 text-neutral-800",
  Planner: "border-sky-200 bg-sky-50 text-sky-900",
  Scout: "border-emerald-200 bg-emerald-50 text-emerald-900",
  Analyst: "border-amber-200 bg-amber-50 text-amber-900",
  Skeptic: "border-rose-200 bg-rose-50 text-rose-900",
  Operator: "border-cyan-200 bg-cyan-50 text-cyan-900",
  Archivist: "border-stone-200 bg-stone-50 text-stone-900",
};

function artifactLabel(type: string): string {
  return type.replace(/_/g, " ");
}

export function TaskRoomPanel({ plan }: { plan: StudioPlan | null }) {
  if (!plan || plan.mode !== "studio") return null;

  const basePath = `.koraku/runs/${plan.run_slug}/`;
  const roles = plan.roles.slice(0, 8);
  const artifacts = plan.artifacts.slice(0, 8);
  const gates = plan.approval_gates.slice(0, 4);

  return (
    <section className="mb-6 rounded border border-neutral-200 bg-[#fbfaf7] text-koraku-ink shadow-[0_1px_0_rgba(15,23,42,0.04)]">
      <div className="border-b border-neutral-200 px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-neutral-500">
              <FolderKanban className="h-3.5 w-3.5" aria-hidden />
              Task room
            </div>
            <h2 className="mt-1 truncate text-base font-bold tracking-tight">
              {plan.title}
            </h2>
            <p className="mt-1 text-xs font-medium text-neutral-500">
              {basePath}
            </p>
          </div>
          <div className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-2.5 py-1 text-xs font-bold text-neutral-700">
            <Route className="h-3.5 w-3.5 text-neutral-500" aria-hidden />
            {plan.reason}
          </div>
        </div>
      </div>

      <div className="grid gap-0 divide-y divide-neutral-200 md:grid-cols-[1fr_1.1fr] md:divide-x md:divide-y-0">
        <div className="px-4 py-4">
          <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-neutral-500">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
            Roles
          </div>
          <div className="flex flex-wrap gap-2">
            {roles.map((role) => (
              <span
                key={role.name}
                title={role.objective}
                className={clsx(
                  "rounded-full border px-2.5 py-1 text-xs font-bold",
                  ROLE_TONE[role.name] ?? "border-neutral-200 bg-white text-neutral-700",
                )}
              >
                {role.name}
              </span>
            ))}
          </div>

          {gates.length > 0 ? (
            <div className="mt-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-neutral-500">
                <KeyRound className="h-3.5 w-3.5" aria-hidden />
                Approval gates
              </div>
              <ul className="space-y-1.5">
                {gates.map((gate) => (
                  <li key={gate} className="text-xs font-medium leading-snug text-neutral-700">
                    {gate}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="px-4 py-4">
          <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-neutral-500">
            <FileText className="h-3.5 w-3.5" aria-hidden />
            Expected artifacts
          </div>
          <div className="space-y-2">
            {artifacts.map((artifact) => (
              <div
                key={artifact.path}
                className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-neutral-200/80 pb-2 last:border-b-0 last:pb-0"
              >
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs font-semibold text-neutral-800">
                    {artifact.path}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-neutral-500">
                    {artifact.purpose}
                  </p>
                </div>
                <span className="self-start rounded-full bg-white px-2 py-0.5 text-[11px] font-bold capitalize text-neutral-500 ring-1 ring-neutral-200">
                  {artifactLabel(artifact.artifact_type)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
