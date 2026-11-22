export type PlatformCategory =
  | "sosyal"
  | "forum"
  | "oyun"
  | "kod"
  | "medya"
  | "blog"
  | "mesajlaşma"
  | "profesyonel";

export type CheckStatus = "found" | "not_found" | "unknown" | "error";

export type SearchMode = "quick" | "full";

export interface PlatformDef {
  id: string;
  name: string;
  category: PlatformCategory;
  /** Şablonda {username} kullanın. */
  urlTemplate: string;
  method: "HEAD" | "GET";
  /** Bu HTTP kodlarından biri → olası bulundu. */
  foundStatus: number[];
  /** Bu kodlardan biri → bulunamadı. */
  notFoundStatus?: number[];
  /** GET gövdesinde bunlardan biri varsa → bulunamadı (soft 404). */
  forbiddenBodySubstrings?: string[];
  /** Hızlı modda dahil et. */
  quick: boolean;
}

export interface IdentityFieldMatch {
  key: "firstName" | "lastName" | "birthYear" | "birthDate" | "location" | "username";
  label: string;
  matched: boolean;
}

export interface IdentityAnalysis {
  fields: IdentityFieldMatch[];
  matchedCount: number;
  strongMatch: boolean;
  summary: string;
}

export interface PlatformResult {
  platformId: string;
  name: string;
  category: PlatformCategory;
  url: string;
  status: CheckStatus;
  httpStatus?: number;
  responseTimeMs: number;
  error?: string;
  identity?: IdentityAnalysis;
}

export interface PersonHintsInput {
  firstName?: string;
  lastName?: string;
  birthDate?: string;
  location?: string;
}

export interface IdentityHighlight {
  platformName: string;
  url: string;
  summary: string;
  strongMatch: boolean;
  matchedLabels: string[];
}

export interface WebSearchLink {
  engine: string;
  label: string;
  url: string;
}

export interface SuggestedQuery {
  label: string;
  url: string;
}

export interface DuckDuckGoResult {
  title: string;
  url: string;
  snippet?: string;
}

export interface WebHit {
  title: string;
  url: string;
  snippet?: string;
  identityMatch?: {
    matchedLabels: string[];
    strongMatch: boolean;
    summary: string;
  };
}

export type EngineScanStatus = "ok" | "empty" | "blocked" | "error";

export interface EngineScan {
  engine: string;
  label: string;
  results: WebHit[];
  status: EngineScanStatus;
  note?: string;
}

export interface ImageSearchOffer {
  engine: string;
  label: string;
  url: string;
  mode: "text" | "upload";
  note: string;
}

export interface WebSearchPayload {
  links: WebSearchLink[];
  suggestedQueries: SuggestedQuery[];
  engineScans: EngineScan[];
  imageSearch: ImageSearchOffer[];
  /** @deprecated engineScans kullanın */
  duckDuckGoResults?: DuckDuckGoResult[];
  duckDuckGoNote?: string;
}

export interface SearchResponse {
  username: string;
  mode: SearchMode;
  person?: PersonHintsInput;
  platforms: PlatformResult[];
  webSearch: WebSearchPayload;
  identityHighlights: IdentityHighlight[];
  meta: {
    checkedCount: number;
    foundCount: number;
    identityMatchCount: number;
    strongIdentityMatchCount: number;
    engineHitCount: number;
    elapsedMs: number;
  };
}