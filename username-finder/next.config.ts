import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  serverExternalPackages: [
    "sharp",
    "@tensorflow/tfjs",
    "@tensorflow/tfjs-node",
    "@vladmandic/face-api",
  ],
};

export default nextConfig;