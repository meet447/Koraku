"use client";

import clsx from "clsx";
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { stripInlineToolJsonFromAnswer } from "@/lib/stripInlineToolJson";

export function MarkdownBody({
  source,
  className,
}: {
  source: string;
  /** Merged onto the root wrapper (e.g. smaller type in run history cards). */
  className?: string;
}) {
  const cleaned = useMemo(
    () => stripInlineToolJsonFromAnswer(source),
    [source],
  );
  return (
    <div
      className={clsx(
        "koraku-md break-words text-[15px] leading-relaxed text-koraku-ink",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => (
            <h1
              className="mt-6 mb-3 text-xl font-bold tracking-tight text-koraku-ink"
              {...p}
            />
          ),
          h2: (p) => (
            <h2
              className="mt-5 mb-2 text-lg font-bold tracking-tight text-koraku-ink"
              {...p}
            />
          ),
          h3: (p) => (
            <h3 className="mt-4 mb-2 text-base font-bold text-koraku-ink" {...p} />
          ),
          p: (p) => <p className="mb-3 text-neutral-800" {...p} />,
          strong: (p) => (
            <strong className="font-semibold text-koraku-ink" {...p} />
          ),
          ul: (p) => (
            <ul className="mb-3 list-disc space-y-1 pl-5 text-neutral-800" {...p} />
          ),
          ol: (p) => (
            <ol className="mb-3 list-decimal space-y-1 pl-5 text-neutral-800" {...p} />
          ),
          li: (p) => <li className="marker:text-neutral-400" {...p} />,
          a: (p) => (
            <a
              className="font-medium text-koraku-accent underline decoration-koraku-accent/30 underline-offset-2 hover:decoration-koraku-accent"
              {...p}
            />
          ),
          code: ({ className, children, ...rest }) => {
            const block = /language-\w+/.test(String(className || ""));
            if (!block) {
              return (
                <code
                  className="rounded-md bg-neutral-100 px-1.5 py-0.5 font-mono text-[13px] text-koraku-ink"
                  {...rest}
                >
                  {children}
                </code>
              );
            }
            return (
              <code
                className={clsx(
                  "block overflow-x-auto rounded-2xl bg-neutral-50 p-4 font-mono text-[13px] text-koraku-ink",
                  className,
                )}
                {...rest}
              >
                {children}
              </code>
            );
          },
          pre: (p) => (
            <pre className="mb-3 max-w-full overflow-x-auto rounded-2xl" {...p} />
          ),
          blockquote: (p) => (
            <blockquote
              className="mb-3 border-l-2 border-koraku-accent/40 pl-4 text-neutral-600 italic"
              {...p}
            />
          ),
          table: ({ children, ...props }) => (
            <div className="my-4 w-full overflow-x-auto rounded-xl border border-neutral-200/90 bg-white shadow-[0_1px_2px_rgb(0_0_0_/_.04)]">
              <table
                className="w-max min-w-full border-collapse border-neutral-200 text-left text-[13px] leading-snug text-neutral-800"
                {...props}
              >
                {children}
              </table>
            </div>
          ),
          thead: (p) => <thead className="[&_tr]:border-b-2 [&_tr]:border-neutral-200" {...p} />,
          tbody: (p) => <tbody {...p} />,
          tr: (p) => <tr {...p} />,
          th: ({ className, ...p }) => (
            <th
              className={clsx(
                "border border-neutral-200 bg-neutral-50 px-3 py-2.5 text-[13px] font-semibold text-koraku-ink",
                className,
              )}
              {...p}
            />
          ),
          td: ({ className, ...p }) => (
            <td
              className={clsx(
                "border border-neutral-200 bg-white px-3 py-2.5 align-top text-[13px] [&_p]:mb-2 [&_p:last-child]:mb-0",
                className,
              )}
              {...p}
            />
          ),
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
}
