"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Cpu,
  Loader2,
  PanelLeftClose,
  PanelLeft,
  Plug,
  Plus,
  Search,
  Settings2,
  SlidersHorizontal,
  Wand2,
} from "lucide-react";
import clsx from "clsx";
import type { ChatSession } from "@/hooks/useKorakuChat";
import { BrandMark } from "@/components/BrandMark";
import { APP_BASE } from "@/lib/app-path";

const iconStroke = 1.5;

const nav = [
  { label: "New chat", icon: Plus, accent: true },
  { href: `${APP_BASE}/connections`, label: "Connections", icon: Plug },
  { href: `${APP_BASE}/automations`, label: "Automations", icon: Wand2 },
  { href: `${APP_BASE}/personalization`, label: "Personalization", icon: SlidersHorizontal },
  { href: `${APP_BASE}/models`, label: "Models", icon: Cpu },
];

export function Sidebar({
  collapsed,
  onToggleCollapse,
  sessions,
  activeId,
  streamingSessionIds,
  onSelectSession,
  onNewChat,
}: {
  collapsed: boolean;
  onToggleCollapse: () => void;
  sessions: ChatSession[];
  activeId: string;
  streamingSessionIds: string[];
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
}) {
  const pathname = usePathname();
  const streamingSet = new Set(streamingSessionIds);

  return (
    <aside
      className={clsx(
        "flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-[28px] border border-neutral-200/90 bg-[#f7f7f7] transition-[width] duration-200 ease-out",
        // Layered “pill input” border: hairline edge + white halo gap + soft outer stroke + float shadow
        "shadow-[0_0_0_3px_rgb(255_255_255),0_0_0_4px_rgb(229_229_229_/_0.55),0_14px_40px_-14px_rgb(0_0_0_/_0.09)]",
        collapsed ? "w-[3.75rem] px-1.5 py-2.5" : "w-[14rem] p-3",
      )}
    >
      <div
        className={clsx(
          "flex shrink-0 items-center",
          collapsed
            ? "mb-1.5 flex-col gap-1.5"
            : "mb-4 w-full flex-row justify-between gap-2",
        )}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <BrandMark size={36} priority />
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-semibold leading-tight text-neutral-900">
                Koraku
              </p>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-neutral-500 transition hover:bg-white/90 hover:text-neutral-900"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" strokeWidth={iconStroke} />
          ) : (
            <PanelLeftClose className="h-4 w-4" strokeWidth={iconStroke} />
          )}
        </button>
      </div>

      <nav className="flex shrink-0 flex-col gap-0.5">
        {nav.map((item) => {
          const Icon = item.icon;
          if (item.accent) {
            return (
              <button
                key={item.label}
                type="button"
                onClick={onNewChat}
                className={clsx(
                  "flex items-center gap-2.5 rounded-2xl px-2.5 py-2 text-left text-[13px] font-semibold text-neutral-800 transition hover:bg-white/90",
                  collapsed ? "justify-center px-0" : "",
                )}
                title="New chat"
              >
                <Icon
                  className="h-4 w-4 shrink-0 text-neutral-600"
                  strokeWidth={iconStroke}
                />
                {!collapsed && item.label}
              </button>
            );
          }
          if (!("href" in item)) return null;
          const { href } = item as { href: string };
          const active =
            pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-2.5 rounded-2xl px-2.5 py-2 text-left text-[13px] font-semibold transition",
                collapsed && "justify-center px-0",
                active
                  ? "bg-white text-neutral-900 shadow-sm ring-1 ring-neutral-200/70"
                  : "text-neutral-600 hover:bg-white/80 hover:text-neutral-900",
              )}
              title={item.label}
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={iconStroke} />
              {!collapsed && item.label}
            </Link>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="mt-4 flex min-h-0 flex-1 flex-col">
          <div className="mb-2 flex shrink-0 items-center justify-between px-1">
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-neutral-400">
              Chats
            </span>
            <button
              type="button"
              className="rounded-md p-1 text-neutral-400 transition hover:bg-white/80 hover:text-neutral-600"
              aria-label="Search chats"
            >
              <Search className="h-3.5 w-3.5" strokeWidth={iconStroke} />
            </button>
          </div>
          <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto overflow-x-hidden pr-0.5">
            {sessions.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelectSession(s.id)}
                className={clsx(
                  "flex w-full min-w-0 items-center gap-2 rounded-[1.1rem] px-2.5 py-2 text-left text-[13px] font-medium transition",
                  s.id === activeId
                    ? "bg-white text-neutral-900 shadow-sm ring-1 ring-neutral-200/60"
                    : "text-neutral-600 hover:bg-white/70 hover:text-neutral-900",
                )}
              >
                {streamingSet.has(s.id) ? (
                  <Loader2
                    className="h-3.5 w-3.5 shrink-0 animate-spin text-neutral-400"
                    aria-hidden
                  />
                ) : (
                  <span className="h-3.5 w-3.5 shrink-0" aria-hidden />
                )}
                <span className="min-w-0 flex-1 truncate">{s.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className={clsx("mt-auto shrink-0", !collapsed && "border-t border-neutral-200/60 pt-2")}>
        <button
          type="button"
          className={clsx(
            "flex w-full items-center gap-2.5 rounded-2xl px-2.5 py-2 text-left text-[13px] font-semibold text-neutral-600 transition hover:bg-white/80 hover:text-neutral-900",
            collapsed && "justify-center px-0",
          )}
        >
          <Settings2 className="h-4 w-4 shrink-0" strokeWidth={iconStroke} />
          {!collapsed && "Settings"}
        </button>
      </div>
    </aside>
  );
}
