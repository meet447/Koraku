"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth-client";

export function AccountMenu() {
  const router = useRouter();
  const { data, isPending } = authClient.useSession();

  if (isPending) {
    return (
      <span className="text-xs text-neutral-400" aria-live="polite">
        …
      </span>
    );
  }

  if (!data?.user) {
    return (
      <div className="flex items-center gap-2 text-xs font-medium">
        <Link
          href="/sign-in"
          className="rounded-full border border-neutral-200 px-3 py-1.5 text-koraku-ink hover:bg-neutral-50"
        >
          Sign in
        </Link>
        <Link
          href="/sign-up"
          className="rounded-full bg-koraku-ink px-3 py-1.5 text-white hover:opacity-90"
        >
          Sign up
        </Link>
      </div>
    );
  }

  return (
    <div className="flex max-w-[14rem] items-center gap-2">
      <span
        className="truncate text-xs text-neutral-600"
        title={data.user.email ?? undefined}
      >
        {data.user.name || data.user.email}
      </span>
      <button
        type="button"
        className="shrink-0 rounded-full border border-neutral-200 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
        onClick={() => {
          void (async () => {
            await authClient.signOut();
            router.refresh();
          })();
        }}
      >
        Sign out
      </button>
    </div>
  );
}
