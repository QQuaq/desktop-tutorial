#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Kurulum / derleme..."
npm ci 2>/dev/null || npm install
npm run build

echo "Sunucu başlıyor (0.0.0.0)..."
node scripts/print-lan-urls.mjs
exec npm run start:lan