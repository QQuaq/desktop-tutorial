import { foldTurkish } from "./profile-hints";
import { normalizeUsername, USERNAME_PATTERN } from "./check-profile";
import type { PersonHintsInput } from "./types";

function slugPart(s: string): string {
  const folded = foldTurkish(s.trim()).replace(/[^a-z0-9]/g, "");
  return folded.slice(0, 24);
}

/** Ad/soyaddan olası profil kullanıcı adları (en fazla 3). */
export function deriveUsernameCandidates(
  firstName: string,
  lastName: string
): string[] {
  const f = slugPart(firstName);
  const l = slugPart(lastName);
  if (f.length < 2 || l.length < 2) return [];

  const raw = [
    `${f}.${l}`,
    `${f}${l}`,
    `${f}_${l}`,
    `${f}-${l}`,
    l,
    f,
    `${f}${l.slice(0, 1)}`,
    `${l}${f}`,
    `${l}.${f}`,
  ];

  const out: string[] = [];
  const seen = new Set<string>();
  for (const candidate of raw) {
    if (candidate.length < 2 || candidate.length > 40) continue;
    if (!USERNAME_PATTERN.test(candidate)) continue;
    const n = normalizeUsername(candidate);
    if (!n || seen.has(n)) continue;
    seen.add(n);
    out.push(n);
    if (out.length >= 3) break;
  }
  return out;
}

export function resolveSearchUsernames(
  rawList: string[],
  person: PersonHintsInput | undefined
): { ok: true; names: string[]; derivedFromName: string[] } | { ok: false; error: string } {
  const explicit: string[] = [];
  const seen = new Set<string>();

  for (const raw of rawList) {
    const n = normalizeUsername(raw);
    if (!n) {
      return {
        ok: false,
        error: `Geçersiz kullanıcı adı: «${raw}».`,
      };
    }
    if (!seen.has(n)) {
      seen.add(n);
      explicit.push(n);
    }
  }

  if (explicit.length > 3) {
    return { ok: false, error: "En fazla 3 kullanıcı adı aranabilir." };
  }

  const first = person?.firstName?.trim() ?? "";
  const last = person?.lastName?.trim() ?? "";
  const derived = first && last ? deriveUsernameCandidates(first, last) : [];
  const derivedFromName: string[] = [];

  const names = [...explicit];
  for (const d of derived) {
    if (names.length >= 3) break;
    if (!seen.has(d)) {
      seen.add(d);
      names.push(d);
      derivedFromName.push(d);
    }
  }

  if (names.length === 0) {
    return {
      ok: false,
      error:
        "En az bir takma ad girin veya ad + soyad yazın (soyaddan tahmini nickler üretilir).",
    };
  }

  return { ok: true, names, derivedFromName };
}