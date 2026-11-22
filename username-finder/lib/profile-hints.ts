export interface PersonHintsInput {
  firstName?: string;
  lastName?: string;
  birthDate?: string;
  location?: string;
}

export interface ParsedPersonHints {
  firstName?: string;
  lastName?: string;
  birthYear?: string;
  birthDateVariants: string[];
  locationTokens: string[];
}

import type { IdentityAnalysis, IdentityFieldMatch } from "./types";

const TR_MAP: Record<string, string> = {
  ç: "c",
  ğ: "g",
  ı: "i",
  ö: "o",
  ş: "s",
  ü: "u",
  Ç: "c",
  Ğ: "g",
  İ: "i",
  I: "i",
  Ö: "o",
  Ş: "s",
  Ü: "u",
};

export function foldTurkish(s: string): string {
  let out = "";
  for (const ch of s) {
    out += TR_MAP[ch] ?? ch;
  }
  return out.toLowerCase();
}

function trimField(s: string | undefined): string | undefined {
  const t = s?.trim();
  return t ? t : undefined;
}

export function parsePersonHints(input: PersonHintsInput): ParsedPersonHints | null {
  const firstName = trimField(input.firstName);
  const lastName = trimField(input.lastName);
  const birthRaw = trimField(input.birthDate);
  const location = trimField(input.location);

  if (!firstName && !lastName && !birthRaw && !location) {
    return null;
  }

  const birthDateVariants: string[] = [];
  let birthYear: string | undefined;

  if (birthRaw) {
    const iso = birthRaw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    const dmy = birthRaw.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})$/);
    if (iso) {
      birthYear = iso[1];
      const [, y, m, d] = iso;
      birthDateVariants.push(`${d.padStart(2, "0")}.${m.padStart(2, "0")}.${y}`);
      birthDateVariants.push(`${d.padStart(2, "0")}/${m.padStart(2, "0")}/${y}`);
      birthDateVariants.push(`${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`);
    } else if (dmy) {
      birthYear = dmy[3];
      const [, d, m, y] = dmy;
      birthDateVariants.push(`${d.padStart(2, "0")}.${m.padStart(2, "0")}.${y}`);
      birthDateVariants.push(`${d.padStart(2, "0")}/${m.padStart(2, "0")}/${y}`);
      birthDateVariants.push(`${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`);
    } else if (/^\d{4}$/.test(birthRaw)) {
      birthYear = birthRaw;
    }
    birthDateVariants.push(birthRaw);
  }

  const locationTokens: string[] = [];
  if (location) {
    const parts = location.split(/[,;/|]+|\s+-\s+/).flatMap((p) => p.trim().split(/\s+/));
    for (const p of parts) {
      const token = p.trim();
      if (token.length >= 3) {
        locationTokens.push(token);
      }
    }
    if (locationTokens.length === 0 && location.length >= 3) {
      locationTokens.push(location);
    }
  }

  return {
    firstName,
    lastName,
    birthYear,
    birthDateVariants: [...new Set(birthDateVariants)],
    locationTokens: [...new Set(locationTokens)],
  };
}

function containsFolded(haystack: string, needle: string): boolean {
  if (!needle || needle.length < 2) return false;
  return foldTurkish(haystack).includes(foldTurkish(needle));
}

export function analyzePageIdentity(
  body: string,
  username: string,
  hints: ParsedPersonHints
): IdentityAnalysis {
  const slice = body.slice(0, 200_000);
  const folded = foldTurkish(slice);

  const fields: IdentityFieldMatch[] = [];

  const firstOk = hints.firstName
    ? containsFolded(slice, hints.firstName)
    : false;
  if (hints.firstName) {
    fields.push({ key: "firstName", label: "Ad", matched: firstOk });
  }

  const lastOk = hints.lastName ? containsFolded(slice, hints.lastName) : false;
  if (hints.lastName) {
    fields.push({ key: "lastName", label: "Soyad", matched: lastOk });
  }

  let birthYearOk = false;
  if (hints.birthYear) {
    birthYearOk =
      folded.includes(hints.birthYear) ||
      slice.includes(hints.birthYear);
    fields.push({
      key: "birthYear",
      label: "Doğum yılı",
      matched: birthYearOk,
    });
  }

  let birthDateOk = false;
  if (hints.birthDateVariants.length > 0) {
    for (const v of hints.birthDateVariants) {
      if (containsFolded(slice, v) || slice.includes(v)) {
        birthDateOk = true;
        break;
      }
    }
    fields.push({
      key: "birthDate",
      label: "Doğum tarihi",
      matched: birthDateOk,
    });
  }

  let locationOk = false;
  const matchedPlaces: string[] = [];
  if (hints.locationTokens.length > 0) {
    for (const token of hints.locationTokens) {
      if (containsFolded(slice, token)) {
        locationOk = true;
        matchedPlaces.push(token);
      }
    }
    fields.push({
      key: "location",
      label: "Yaşadığı yer",
      matched: locationOk,
    });
  }

  const userOk = containsFolded(slice, username);
  fields.push({
    key: "username",
    label: "Kullanıcı adı",
    matched: userOk,
  });

  const matchedCount = fields.filter((f) => f.matched).length;

  const birthSignal = birthYearOk || birthDateOk;
  const strongMatch =
    (birthSignal && locationOk) ||
    matchedCount >= 4 ||
    (firstOk && lastOk && locationOk);

  let summary: string;
  if (matchedCount === 0) {
    summary = "Sayfada girdiğiniz kimlik bilgileriyle örtüşen metin bulunamadı.";
  } else if (strongMatch) {
    const parts = fields.filter((f) => f.matched).map((f) => f.label);
    summary = `Bu profilde güçlü örtüşme: ${parts.join(", ")}. Aynı kişi olabilir — bağlantıyı elle doğrulayın.`;
    if (birthSignal && locationOk) {
      summary = `Doğum bilgisi ve yaşadığı yer bu sayfada geçiyor${matchedPlaces.length ? ` (${matchedPlaces.join(", ")})` : ""}; ${parts.filter((p) => p !== "Yaşadığı yer").join(", ")} ile birlikte kontrol edin.`;
    }
  } else {
    const parts = fields.filter((f) => f.matched).map((f) => f.label);
    summary = `Kısmi eşleşme: ${parts.join(", ")}.`;
  }

  return { fields, matchedCount, strongMatch, summary };
}

export function buildIdentitySearchQuery(
  username: string,
  hints: ParsedPersonHints | null
): string {
  const chunks = [`"${username}"`];
  if (hints?.firstName) chunks.push(`"${hints.firstName}"`);
  if (hints?.lastName) chunks.push(`"${hints.lastName}"`);
  if (hints?.birthYear) chunks.push(hints.birthYear);
  if (hints?.locationTokens[0]) chunks.push(`"${hints.locationTokens[0]}"`);
  return chunks.join(" ");
}