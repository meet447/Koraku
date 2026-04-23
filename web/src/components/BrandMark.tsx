"use client";

import clsx from "clsx";
import Image from "next/image";

const BRAND_SRC = "/icon.png";

export function BrandMark({
  size,
  className,
  priority,
}: {
  size: number;
  className?: string;
  /** Set on first-paint surfaces (sidebar, hero). */
  priority?: boolean;
}) {
  return (
    <span
      className={clsx(
        "inline-flex shrink-0 overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-neutral-200/80",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <Image
        src={BRAND_SRC}
        alt="Koraku"
        width={size}
        height={size}
        className="object-contain p-[10%]"
        priority={priority}
        sizes={`${size}px`}
      />
    </span>
  );
}
