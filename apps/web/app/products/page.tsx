import { CatalogView } from "@/components/commerce/catalog-view";

export const metadata = { title: "All Products — Clothist" };

export default function ProductsPage() {
  // No `gender` prop → CatalogView omits the gender param and the API
  // returns every product across men/women/unisex.
  return <CatalogView title="Products." eyebrow="00 / Catalog · All" />;
}
