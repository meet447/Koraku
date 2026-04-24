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
    <Image
      src={BRAND_SRC}
      alt="Koraku"
      width={size}
      height={size}
      className={clsx("shrink-0 object-contain", className)}
      priority={priority}
      sizes={`${size}px`}
    />
  );
}
