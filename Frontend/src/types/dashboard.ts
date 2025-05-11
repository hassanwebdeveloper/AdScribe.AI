export interface BestAdPrediction {
  ad_id: string;
  ad_name: string;
  ad_title?: string;  // Add ad_title as an optional field
  score: number;
  average_metrics: {
    roas: number;
    ctr: number;
    cpc: number;
    cpm: number;
    conversions: number;
    revenue: number;
    spend: number;
  };
} 