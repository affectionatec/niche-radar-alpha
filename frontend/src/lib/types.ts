export interface SourceHealth {
  source: string;
  status: string;
  last_run: string;
  items: number;
}

export interface SystemStatus {
  raw_items: number;
  active_niches: number;
  last_collection: string | null;
  collection_cycle: number;
  sources: SourceHealth[];
}

export interface NicheScore {
  niche_id: string;
  keyword: string;
  aliases: string[];
  llm_score: number;
  llm_reasoning: string;
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

export type JobStatus = 'pending' | 'running' | 'done' | 'failed';

export interface Job {
  id: string;
  step: string;
  status: JobStatus;
  created_at: string;
  completed_at: string | null;
}

export interface JobDetail extends Job {
  logs: string[];
}

export interface ReportFile {
  filename: string;
  size: number;
  modified: number;
}

export interface LLMSettings {
  llm_provider: string;
  llm_model: string;
  llm_base_url: string;
  llm_api_key_set: boolean;
}
