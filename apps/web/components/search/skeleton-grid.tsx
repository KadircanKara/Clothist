"use client";

type Props = { count?: number };

export function SkeletonGrid({ count = 8 }: Props) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          aria-hidden
          className="anim-fade"
          style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
        >
          <div className="skeleton aspect-[3/4] w-full hairline" />
          <div className="mt-3 flex flex-col gap-2">
            <div className="skeleton h-3 w-1/3" />
            <div className="skeleton h-4 w-2/3" />
            <div className="skeleton h-4 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}
