import Link from "next/link";
import { BrandMark } from "@/components/BrandMark";
import { APP_BASE } from "@/lib/app-path";

export default function LandingPage() {
  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#fafafa] text-koraku-ink">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.45]"
        aria-hidden
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(251, 146, 60, 0.18), transparent), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(253, 186, 116, 0.12), transparent)",
        }}
      />
      <div className="relative mx-auto flex min-h-dvh max-w-3xl flex-col px-6 py-20">
        <header className="mb-16 flex flex-col items-center text-center">
          <div className="mb-6 flex justify-center">
            <BrandMark size={80} priority />
          </div>
          <h1 className="mb-3 text-4xl font-bold tracking-tight text-neutral-900 sm:text-5xl">
            Koraku
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-neutral-600">
            A light workspace for agents: chat, tools, workspace files, and
            automations — organized in one place.
          </p>
        </header>

        <div className="mx-auto flex w-full max-w-md flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href={`${APP_BASE}`}
            className="inline-flex h-12 items-center justify-center rounded-full bg-koraku-ink px-8 text-sm font-semibold text-white shadow-sm transition hover:opacity-90"
          >
            Open app
          </Link>
          <Link
            href="/sign-in"
            className="inline-flex h-12 items-center justify-center rounded-full border border-neutral-300 bg-white px-8 text-sm font-semibold text-neutral-800 shadow-sm transition hover:bg-neutral-50"
          >
            Sign in
          </Link>
        </div>

        <p className="mt-10 text-center text-sm text-neutral-500">
          New here?{" "}
          <Link href="/sign-up" className="font-medium text-koraku-accent underline">
            Create an account
          </Link>
        </p>

        <footer className="mt-auto pt-24 text-center text-xs text-neutral-400">
          The app requires sign-in. You will be redirected from{" "}
          <span className="font-mono text-neutral-500">{APP_BASE}</span> if you are
          not signed in.
        </footer>
      </div>
    </main>
  );
}
