export interface SourceHealth {
  source: string;
  status: string;
  last_run: string;
  items: number;
}

export interface SystemStatus {
  raw_items: number;
  active_niches: number;
  scores_recorded: number;
  last_collection: string | null;
  collection_cycle: number;
  sources: SourceHealth[];
}

export interface NicheScore {
  score_id: string;
  niche_id: string;
  keyword: string;
  aliases: string[];
  engagement: number;
  search_trend: number;
  content_gap: number;
  market_traction: number;
  composite_score: number;
  scored_at: string;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  tier: 'high_priority' | 'watchlist' | 'archive';
}

export interface RawItem {
  id: string;
  source: string;
  source_id: string;
  title: string | null;
  body: string | null;
  url: string | null;
  score: number | null;
  comment_count: number | null;
  collected_at: string;
  keyphrase: string;
  relevance_score: number;
}

export interface NicheDetail {
  niche: NicheScore;
  items: RawItem[];
}
