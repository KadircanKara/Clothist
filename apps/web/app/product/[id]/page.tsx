import { PdpView } from "@/components/product/pdp-view";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PdpView idOrSlug={id} />;
}
