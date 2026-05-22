export function Wordmark({ className }: { className?: string }) {
  return (
    <h1
      className={[
        "font-serif italic tracking-tightest leading-[0.9]",
        "text-[9vw] sm:text-[6.5vw] md:text-[5.5rem] lg:text-[7rem]",
        className,
      ].filter(Boolean).join(" ")}
    >
      Clothist<span className="text-accent">.</span>
    </h1>
  );
}
