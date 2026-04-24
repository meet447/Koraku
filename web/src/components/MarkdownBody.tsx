"use client";

import clsx from "clsx";
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { stripInlineToolJsonFromAnswer } from "@/lib/stripInlineToolJson";

export function MarkdownBody({ source }: { source: string }) {
  const cleaned = useMemo(
    () => stripInlineToolJsonFromAnswer(source),
    [source],
  );
  return (
    <div className="koraku-md break-words text-[15px] leading-relaxed text-koraku-ink">
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
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
}
