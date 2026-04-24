"use client";

export default function ModelsPage() {
  return (
    <main className="min-h-0 flex-1 overflow-y-auto px-6 py-10">
        <div className="mx-auto max-w-2xl">
          <h1 className="text-3xl font-bold tracking-tight text-koraku-ink">
            Models
          </h1>
          <p className="mt-2 text-sm font-medium text-koraku-muted">
            Choose which models Koraku can use for agent turns. Connect accounts
            to unlock more capacity.
          </p>

          <section className="mt-10 space-y-6">
            <div className="rounded-3xl bg-koraku-panel p-5">
              <h2 className="text-sm font-bold text-neutral-600">Agent models</h2>
              <div className="mt-4 space-y-2 rounded-2xl bg-white p-2 ring-1 ring-neutral-200/80">
                {[
                  "Claude Sonnet 4.6",
                  "Claude Opus 4.6",
                  "GPT-5.4",
                  "Kimi K2",
                ].map((name) => (
                  <div
                    key={name}
                    className="flex items-center justify-between rounded-2xl px-3 py-3 hover:bg-neutral-50"
                  >
                    <span className="text-sm font-bold text-koraku-ink">{name}</span>
                    <button
                      type="button"
                      className="relative h-7 w-12 rounded-full bg-neutral-900 after:absolute after:top-1 after:right-1 after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-transform"
                      aria-pressed
                    />
                  </div>
                ))}
                <div className="flex items-center justify-between rounded-2xl px-3 py-3 hover:bg-neutral-50">
                  <div>
                    <p className="text-sm font-bold text-koraku-ink">Auto</p>
                    <p className="text-xs font-medium text-koraku-muted">Always on</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-3xl bg-koraku-panel p-5">
              <h2 className="text-sm font-bold text-neutral-600">Subscriptions</h2>
              <p className="mt-1 text-xs font-medium text-koraku-muted">
                Link ChatGPT or other plans so Koraku can route requests cleanly.
              </p>
              <div className="mt-4 flex items-center justify-between rounded-2xl bg-white p-4 ring-1 ring-neutral-200/80">
                <span className="text-sm font-bold text-koraku-ink">
                  ChatGPT Plus / Pro
                </span>
                <button
                  type="button"
                  className="rounded-full bg-neutral-900 px-4 py-2 text-xs font-semibold text-white hover:bg-neutral-800"
                >
                  Connect
                </button>
              </div>
            </div>

            <div className="rounded-3xl bg-koraku-panel p-5">
              <h2 className="text-sm font-bold text-neutral-600">API keys</h2>
              <p className="mt-1 text-xs font-medium text-koraku-muted">
                Keys stay on this machine in your Python agent configuration
                (environment / <code className="font-mono">.env</code>). This UI is
                a visual mirror only.
              </p>
              <div className="mt-4 flex items-center justify-between rounded-2xl bg-white p-4 ring-1 ring-neutral-200/80">
                <span className="text-sm font-bold text-koraku-ink">
                  OpenAI-compatible endpoint
                </span>
                <button
                  type="button"
                  className="rounded-full bg-neutral-900 px-4 py-2 text-xs font-semibold text-white hover:bg-neutral-800"
                >
                  Configure
                </button>
              </div>
            </div>
          </section>
        </div>
      </main>
  );
}
