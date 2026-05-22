/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "*.hm.com" },
      { protocol: "https", hostname: "*.zara.net" },
      { protocol: "https", hostname: "image.uniqlo.com" },
    ],
  },
};

export default nextConfig;
