"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { APP_BASE } from "@/lib/app-path";

function readNextPath(): string {
  if (typeof window === "undefined") return APP_BASE;
  const raw = new URLSearchParams(window.location.search).get("next");
  if (raw && raw.startsWith("/app")) return raw;
  return APP_BASE;
}

export default function SignUpPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { error: err } = await authClient.signUp.email({
        name: name.trim() || email.trim().split("@")[0] || "User",
        email: email.trim(),
        password,
      });
      if (err) {
        setError(err.message || "Sign up failed");
        return;
      }
      router.push(readNextPath());
      router.refresh();
    } catch (ex) {
      setError(String((ex as Error)?.message || ex));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6 py-16">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-koraku-ink">
        Create account
      </h1>
      <p className="mb-8 text-sm text-neutral-600">
        Already have one?{" "}
        <Link href="/sign-in" className="text-koraku-accent underline">
          Sign in
        </Link>
      </p>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-neutral-700">Name</span>
          <input
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-lg border border-neutral-200 px-3 py-2 text-[15px] outline-none ring-koraku-accent/30 focus:ring-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-neutral-700">Email</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-neutral-200 px-3 py-2 text-[15px] outline-none ring-koraku-accent/30 focus:ring-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-neutral-700">Password</span>
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-neutral-200 px-3 py-2 text-[15px] outline-none ring-koraku-accent/30 focus:ring-2"
          />
        </label>
        {error ? (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-koraku-ink px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="mt-8 text-center text-sm text-neutral-500">
        <Link href="/" className="underline">
          Home
        </Link>
      </p>
    </main>
  );
}
