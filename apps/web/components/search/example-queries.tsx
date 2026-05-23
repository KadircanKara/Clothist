"use client";

const QUERIES = [
  "black cargo pants under $100",
  "minimalist hoodie 4300₺ altında",
  "waterproof jacket with hidden pockets",
  "minimalist sneakers under €100",
  "cheapest tshirt",
];

type Props = {
  onPick: (q: string) => void;
  fxDate?: string | null;
};

export function ExampleQueries({ onPick, fxDate }: Props) {
  return (
    <div className="mt-10">
      <div className="flex items-baseline justify-between hairline-b pb-2">
        <span className="kicker">Try one</span>
        {fxDate && <span className="mono-fx">FX {fxDate}</span>}
      </div>
      <ul className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {QUERIES.map((q) => (
          <li key={q}>
            <button
              type="button"
              onClick={() => onPick(q)}
              className="group inline-flex items-center gap-2 px-1 py-1 text-left transition-colors"
            >
              <span className="font-mono text-[11px] uppercase tracking-widest text-muted group-hover:text-foreground">›</span>
              <span className="font-serif italic text-base text-foreground/85 group-hover:text-foreground">
                &ldquo;{q}&rdquo;
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
