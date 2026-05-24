export interface SourceHealth {
  source: string;
  status: string;
  last_run: string;
  items: number;
}

export interface SourceFreshness {
  source: string;
  items: number;
  oldest_posted: string | null;
  newest_posted: string | null;
  newest_age_hours: number | null;
}

export interface FreshnessSummary {
  analysis_window_days: number;
  rules: {
    reddit_hours: number;
    hn_hours: number;
    github_hours: number;
    google_trends_hours: number;
    youtube_hours: number;
  };
  per_source: SourceFreshness[];
}

export interface SystemStatus {
  raw_items: number;
  active_niches: number;
  last_collection: string | null;
  collection_cycle: number;
  sources: SourceHealth[];
  freshness?: FreshnessSummary;
}

export interface PainPoint {
  pain: string;
  quote: string;
  item_id: string;
}

export interface NicheScore {
  id: string;
  niche_id: string;
  keyword: string;
  aliases: string[];
  llm_score: number;
  llm_reasoning: string;
  tool_concept: string;
  target_audience: string;
  build_complexity: number | null;
  monetization: string;
  pain_points: PainPoint[];
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  tier: 'high_priority' | 'watchlist' | 'archive';
  // v4 enhancements
  verdict?: string | null;
  momentum_label?: 'growing' | 'stable' | 'declining' | null;
  momentum_ratio?: number | null;
  is_shortlisted?: boolean;
}

export interface WebValidation {
  verdict: 'validated_gap' | 'crowded_market' | 'expensive_incumbents' | 'unclear';
  evidence: { query: string; top_results: { title: string; url: string; snippet: string }[] }[];
}

export interface NicheAnalysis {
  verdict: string | null;
  opportunity_score: number | null;
  weighted_score: number | null;
  pipeline_tier: string | null;
  feasibility_score: number | null;
  web_validation: WebValidation | null;
  go_no_go_rationale: string | null;
  prd: Record<string, unknown> | null;
  brief: Record<string, unknown> | null;
  a4_scores: A4Scores | null;
}

export interface A4DimensionScore {
  score: number | null;
  rationale: string | null;
}

export interface A4Scores {
  problem_clarity: A4DimensionScore | null;
  market_size: A4DimensionScore | null;
  willingness_to_pay: A4DimensionScore | null;
  competition_gap: A4DimensionScore | null;
  technical_feasibility: A4DimensionScore | null;
  distribution_clarity: A4DimensionScore | null;
  trend_momentum: A4DimensionScore | null;
}

export interface ScoringWeights {
  problem_clarity: number;
  market_size: number;
  willingness_to_pay: number;
  competition_gap: number;
  technical_feasibility: number;
  distribution_clarity: number;
  trend_momentum: number;
}

export interface SourceCredentialField {
  key: string;
  label: string;
  secret: boolean;
  optional: boolean;
  help: string;
}

export interface SourceStatus {
  slug: string;
  schema: SourceCredentialField[];
  credentials_set: Record<string, string>;
  required_missing: string[];
  configured: boolean;
  last_success: string | null;
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
  niche: NicheScore & { is_shortlisted: boolean; analysis: NicheAnalysis | null };
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
