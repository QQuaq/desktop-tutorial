#!/usr/bin/env bash
# GitHub Pages’i açar (repo public + main/docs). Kendi hesabında çalıştır.
set -euo pipefail

REPO="${1:-QQuaq/desktop-tutorial}"

if ! command -v gh >/dev/null; then
  echo "Hata: GitHub CLI (gh) yüklü değil. https://cli.github.com/"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Önce: gh auth login"
  exit 1
fi

echo "==> Repo: $REPO"
VIS=$(gh api "repos/$REPO" --jq .visibility)
echo "    Şu an: $VIS"

if [[ "$VIS" != "public" ]]; then
  echo "==> Repo public yapılıyor (private Pages dışarıya 404 verir)…"
  gh repo edit "$REPO" --visibility public
fi

echo "==> GitHub Pages: main /docs"
if gh api "repos/$REPO/pages" >/dev/null 2>&1; then
  gh api -X PUT "repos/$REPO/pages" \
    -f build_type=legacy \
    -f "source[branch]=main" \
    -f "source[path]=/docs"
else
  gh api -X POST "repos/$REPO/pages" \
    -f build_type=legacy \
    -f "source[branch]=main" \
    -f "source[path]=/docs"
fi

echo ""
echo "Tamam. 1–3 dakika bekle, sonra aç:"
echo "  https://qquaq.github.io/desktop-tutorial/"