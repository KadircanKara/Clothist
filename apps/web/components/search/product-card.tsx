import Image from "next/image";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/lib/utils";
import type { Product } from "@/lib/types";

export function ProductCard({ product }: { product: Product }) {
  const price = formatPrice(product.price, product.currency);
  const original = formatPrice(product.original_price, product.currency);
  const onSale = original && price && original !== price;

  return (
    <a
      href={product.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block"
    >
      <div className="relative aspect-[3/4] w-full overflow-hidden bg-bg-alt hairline">
        {product.image_url ? (
          <Image
            src={product.image_url}
            alt={product.title}
            fill
            sizes="(max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
            className="object-cover transition-transform duration-[900ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center font-mono text-[11px] uppercase tracking-widest text-muted">
            No image
          </div>
        )}

        {/* Corner labels */}
        <div className="absolute left-2 top-2 flex flex-col gap-1">
          {onSale && <Badge variant="accent">Sale</Badge>}
        </div>
        <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
          {!product.in_stock && <Badge variant="outline">Out of stock</Badge>}
        </div>

        {/* Hover scrim with quick info */}
        <div className="absolute inset-x-0 bottom-0 translate-y-2 opacity-0 transition-all duration-500 group-hover:translate-y-0 group-hover:opacity-100">
          <div className="bg-gradient-to-t from-background via-background/85 to-transparent px-3 pb-3 pt-8">
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted">
              View at {product.retailer === "seed" ? "retailer" : product.retailer.toUpperCase()} →
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-1 pt-3">
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted truncate">
            {product.brand ?? product.retailer}
          </span>
          {product.category && (
            <span className="font-mono text-[11px] uppercase tracking-widest text-muted shrink-0">
              {product.category}
            </span>
          )}
        </div>
        <h3 className="line-clamp-2 text-[17px] font-medium leading-snug">
          <span className="link-reveal">{product.title}</span>
        </h3>
        <div className="flex items-baseline gap-2 pt-1">
          {price && <span className="font-mono text-base">{price}</span>}
          {onSale && (
            <span className="font-mono text-xs text-muted line-through">{original}</span>
          )}
        </div>
      </div>
    </a>
  );
}
