import Image from "next/image";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/lib/utils";
import type { Product } from "@/lib/types";

type Props = {
  product: Product;
  /** Features the user/LLM requested — used to render the matched-features ribbon. */
  requestedFeatures?: string[];
};

function humanizeFeature(token: string): string {
  return token.replace(/_/g, " ");
}

export function ProductCard({ product, requestedFeatures = [] }: Props) {
  const price = formatPrice(product.price, product.currency);
  const original = formatPrice(product.original_price, product.currency);
  const priceUsd =
    product.price_usd && product.currency && product.currency !== "USD"
      ? formatPrice(product.price_usd, "USD")
      : null;
  const onSale = original && price && original !== price;

  const productFeatures = product.attributes?.features ?? [];
  const matched = requestedFeatures.filter((f) => productFeatures.includes(f));
  const extra = matched.length - 2;

  const v = product.attributes?.variants;
  const hero = v && v.length > 0 ? v[0].image_url : product.image_url;

  return (
    <Link href={`/product/${product.retailer_product_id}`} className="group block">
      <div className="relative aspect-[3/4] w-full overflow-hidden bg-bg-alt hairline">
        {hero ? (
          <Image
            src={hero}
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

        <div className="absolute left-2 top-2 flex flex-col gap-1">
          {onSale && <Badge variant="accent">Sale</Badge>}
        </div>
        <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
          {!product.in_stock && <Badge variant="outline">Out of stock</Badge>}
        </div>

        <div
          aria-hidden
          className="absolute inset-x-0 bottom-0 translate-y-2 opacity-0 transition-all duration-500 group-hover:translate-y-0 group-hover:opacity-100"
        >
          <div className="bg-gradient-to-t from-background via-background/85 to-transparent px-3 pb-3 pt-8">
            <p className="font-mono text-[11px] uppercase tracking-widest text-muted">
              View product →
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
        <div className="flex flex-col gap-0.5 pt-1">
          <div className="flex items-baseline gap-2">
            {price && <span className="font-mono text-base">{price}</span>}
            {onSale && (
              <span className="font-mono text-xs text-muted line-through">{original}</span>
            )}
          </div>
          {priceUsd && (
            <span className="mono-fx normal-case">≈ {priceUsd} USD</span>
          )}
        </div>
        {matched.length > 0 && (
          <div className="pt-1 font-mono text-[11px] uppercase tracking-widest text-muted">
            {matched.slice(0, 2).map((f, i) => (
              <span key={f}>
                {i > 0 && " "}
                ✓ {humanizeFeature(f)}
              </span>
            ))}
            {extra > 0 && <span> +{extra}</span>}
          </div>
        )}
      </div>
    </Link>
  );
}
