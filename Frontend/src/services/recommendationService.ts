import api from '@/utils/api';

export interface RecommendationGoal {
  metric: string;
  target_improvement: number;
  current_value?: number;
  target_value?: number;
  timeframe_days?: number;
}

export interface PerformanceMetrics {
  roas?: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
  spend?: number;
  revenue?: number;
  clicks?: number;
  impressions?: number;
  purchases?: number;
  conversion_rate?: number;
  frequency?: number;
  reach?: number;
}

export interface CreativeMetadata {
  hook_type?: string;
  hook_content?: string;
  tone_category?: string;
  visual_style?: string;
  power_elements?: string[];
  cta_type?: string;
  product_focus?: string;
  duration_seconds?: number;
  voice_tone?: string;
}

export interface RecommendationAction {
  type: string;
  priority: number;
  title: string;
  description: string;
  expected_impact?: string;
  confidence_score?: number;
  implementation_effort?: string;
}

export interface AIRecommendation {
  suggestion: string;
  reasoning: string;
  specific_changes?: any;
  confidence_score?: number;
}

export interface AdRecommendation {
  _id: string;
  user_id: string;
  ad_id: string;
  ad_name?: string;
  campaign_id?: string;
  video_id?: string;
  performance_summary: PerformanceMetrics;
  creative_metadata?: CreativeMetadata;
  goal: RecommendationGoal;
  fixed_recommendations: RecommendationAction[];
  ai_recommendations: AIRecommendation[];
  predicted_performance?: PerformanceMetrics;
  feature_importance?: Record<string, number>;
  generated_at: string;
  status: string;
  implementation_notes?: string;
}

export interface RecommendationRequest {
  ad_ids?: string[];
  goal: RecommendationGoal;
  force_refresh: boolean;
  include_predictions: boolean;
}

export interface QuickAnalysisResponse {
  ad_id: string;
  ad_name?: string;
  current_performance: PerformanceMetrics;
  goal: {
    metric: string;
    current_value?: number;
    target_value?: number;
    improvement_needed: number;
  };
  top_recommendations: Array<{
    title: string;
    description: string;
    expected_impact?: string;
    priority: number;
  }>;
  ai_insights: Array<{
    suggestion: string;
    confidence?: number;
  }>;
}

export interface RecommendationFilters {
  status?: string;
  ad_id?: string;
  limit?: number;
}

class RecommendationService {
  private baseUrl = '/recommendations';

  async generateRecommendations(request: RecommendationRequest): Promise<AdRecommendation[]> {
    try {
      const response = await api.post(`${this.baseUrl}/generate`, request);
      return response.data;
    } catch (error) {
      console.error('Error generating recommendations:', error);
      throw error;
    }
  }

  async getRecommendations(filters: RecommendationFilters = {}): Promise<AdRecommendation[]> {
    try {
      const params = new URLSearchParams();
      
      if (filters.status) params.append('status', filters.status);
      if (filters.ad_id) params.append('ad_id', filters.ad_id);
      if (filters.limit) params.append('limit', filters.limit.toString());

      const response = await api.get(`${this.baseUrl}/?${params.toString()}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching recommendations:', error);
      throw error;
    }
  }

  async getRecommendation(id: string): Promise<AdRecommendation> {
    try {
      const response = await api.get(`${this.baseUrl}/${id}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching recommendation:', error);
      throw error;
    }
  }

  async updateStatus(
    id: string, 
    status: string, 
    implementation_notes?: string
  ): Promise<{ message: string }> {
    try {
      const body: any = { status };
      if (implementation_notes) {
        body.implementation_notes = implementation_notes;
      }

      const response = await api.put(`${this.baseUrl}/${id}/status`, body);
      return response.data;
    } catch (error) {
      console.error('Error updating recommendation status:', error);
      throw error;
    }
  }

  async quickAnalysis(
    ad_id: string, 
    goal: RecommendationGoal
  ): Promise<QuickAnalysisResponse> {
    try {
      const response = await api.post(`${this.baseUrl}/quick-analysis`, {
        ad_id,
        goal
      });
      return response.data;
    } catch (error) {
      console.error('Error performing quick analysis:', error);
      throw error;
    }
  }

  // New methods for stored ML recommendations
  async getStoredRecommendations(): Promise<any[]> {
    try {
      const response = await api.get(`${this.baseUrl}/latest`);
      return response.data;
    } catch (error) {
      console.error('Error fetching stored recommendations:', error);
      throw error;
    }
  }

  async getStoredRecommendationsByBatch(batchId: string): Promise<any> {
    try {
      const response = await api.get(`${this.baseUrl}/stored/${batchId}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching stored recommendations by batch:', error);
      throw error;
    }
  }

  async getAllStoredRecommendations(): Promise<any[]> {
    try {
      // Get all stored recommendation batches
      const response = await api.get(`${this.baseUrl}/stored-history`);
      return response.data;
    } catch (error) {
      console.error('Error fetching all stored recommendations:', error);
      return []; // Return empty array if endpoint doesn't exist yet
    }
  }

  // Helper methods for grouping and organizing stored recommendations
  groupRecommendationsByDate(recommendations: any[]): Record<string, any[]> {
    const grouped: Record<string, any[]> = {};
    
    recommendations.forEach(rec => {
      const date = new Date(rec.generated_at).toISOString().split('T')[0];
      if (!grouped[date]) {
        grouped[date] = [];
      }
      grouped[date].push(rec);
    });
    
    return grouped;
  }

  groupRecommendationsByStrategy(recommendations: any[]): Record<string, any[]> {
    const grouped: Record<string, any[]> = {
      ctr_improvements: [],
      spend_optimizations: [],
      efficiency_improvements: [],
      conversion_improvements: []
    };
    
    recommendations.forEach(rec => {
      // Group by strategy based on recommendation structure
      if (rec.ctr_improvements?.recommendations?.length > 0) {
        grouped.ctr_improvements.push(...rec.ctr_improvements.recommendations);
      }
      if (rec.spend_optimizations?.recommendations?.length > 0) {
        grouped.spend_optimizations.push(...rec.spend_optimizations.recommendations);
      }
      if (rec.efficiency_improvements?.recommendations?.length > 0) {
        grouped.efficiency_improvements.push(...rec.efficiency_improvements.recommendations);
      }
      if (rec.conversion_improvements?.recommendations?.length > 0) {
        grouped.conversion_improvements.push(...rec.conversion_improvements.recommendations);
      }
    });
    
    return grouped;
  }

  getStrategyDisplayName(strategy: string): string {
    const strategyNames: Record<string, string> = {
      ctr_improvements: 'CTR Improvements',
      spend_optimizations: 'Spend Optimizations',
      efficiency_improvements: 'Efficiency Improvements',
      conversion_improvements: 'Conversion Improvements'
    };
    return strategyNames[strategy] || strategy;
  }

  getStrategyDescription(strategy: string): string {
    const descriptions: Record<string, string> = {
      ctr_improvements: 'Optimize creative elements to improve click-through rates',
      spend_optimizations: 'Adjust budget allocation for maximum ROAS',
      efficiency_improvements: 'Reduce cost per click and cost per mille',
      conversion_improvements: 'Enhance conversion rates and purchase volume'
    };
    return descriptions[strategy] || '';
  }

  getStrategyIcon(strategy: string): string {
    const icons: Record<string, string> = {
      ctr_improvements: 'Target',
      spend_optimizations: 'DollarSign',
      efficiency_improvements: 'TrendingUp',
      conversion_improvements: 'ShoppingCart'
    };
    return icons[strategy] || 'Lightbulb';
  }

  // Helper methods
  getPriorityColor(priority: number): string {
    switch (priority) {
      case 1: return 'bg-red-100 text-red-800 border-red-200';
      case 2: return 'bg-orange-100 text-orange-800 border-orange-200';
      case 3: return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 4: return 'bg-blue-100 text-blue-800 border-blue-200';
      case 5: return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  }

  getPriorityLabel(priority: number): string {
    switch (priority) {
      case 1: return 'Critical';
      case 2: return 'High';
      case 3: return 'Medium';
      case 4: return 'Low';
      case 5: return 'Optional';
      default: return 'Unknown';
    }
  }

  getStatusColor(status: string): string {
    switch (status) {
      case 'active': return 'bg-blue-100 text-blue-800';
      case 'implemented': return 'bg-green-100 text-green-800';
      case 'archived': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  }

  formatMetric(metric: string, value: number): string {
    switch (metric) {
      case 'roas':
        return `${value.toFixed(2)}x`;
      case 'ctr':
        return `${(value * 100).toFixed(2)}%`;
      case 'conversion_rate':
        return `${(value * 100).toFixed(2)}%`;
      case 'cpc':
      case 'cpm':
      case 'spend':
      case 'revenue':
        return `$${value.toFixed(2)}`;
      case 'clicks':
      case 'impressions':
      case 'purchases':
      case 'reach':
        return value.toLocaleString();
      case 'frequency':
        return value.toFixed(1);
      default:
        return value.toString();
    }
  }

  getMetricTrend(current: number, target: number): 'up' | 'down' | 'neutral' {
    if (target > current) return 'up';
    if (target < current) return 'down';
    return 'neutral';
  }

  calculateImprovementPercentage(current: number, target: number): number {
    if (current === 0) return 0;
    return ((target - current) / current) * 100;
  }

  // Validation helpers
  isValidMetric(metric: string): boolean {
    const validMetrics = ['roas', 'ctr', 'cpc', 'cpm', 'conversion_rate', 'frequency'];
    return validMetrics.includes(metric);
  }

  isValidStatus(status: string): boolean {
    const validStatuses = ['active', 'implemented', 'archived'];
    return validStatuses.includes(status);
  }

  isValidPriority(priority: number): boolean {
    return priority >= 1 && priority <= 5;
  }

  // Creative analysis helpers
  extractPowerElements(powerPhrasesString?: string): string[] {
    if (!powerPhrasesString) return [];
    
    const elements: string[] = [];
    const lowerCase = powerPhrasesString.toLowerCase();
    
    if (lowerCase.includes('urgency') || lowerCase.includes('limited') || lowerCase.includes('now')) {
      elements.push('Urgency');
    }
    if (lowerCase.includes('social proof') || lowerCase.includes('testimonial') || lowerCase.includes('review')) {
      elements.push('Social Proof');
    }
    if (lowerCase.includes('guarantee') || lowerCase.includes('risk reversal') || lowerCase.includes('refund')) {
      elements.push('Risk Reversal');
    }
    if (lowerCase.includes('exclusive') || lowerCase.includes('special') || lowerCase.includes('vip')) {
      elements.push('Exclusivity');
    }
    if (lowerCase.includes('free') || lowerCase.includes('bonus') || lowerCase.includes('gift')) {
      elements.push('Value Add');
    }
    
    return elements;
  }

  classifyHookType(hook?: string): string {
    if (!hook) return 'Unknown';
    
    const lowerCase = hook.toLowerCase();
    
    if (lowerCase.includes('feel') || lowerCase.includes('story') || lowerCase.includes('emotional')) {
      return 'Emotional';
    }
    if (lowerCase.includes('how to') || lowerCase.includes('learn') || lowerCase.includes('discover')) {
      return 'Informational';
    }
    if (lowerCase.includes('problem') || lowerCase.includes('struggle') || lowerCase.includes('solution')) {
      return 'Problem-solution';
    }
    if (lowerCase.includes('?') || lowerCase.includes('have you') || lowerCase.includes('do you')) {
      return 'Question';
    }
    
    return 'Direct';
  }

  classifyTone(tone?: string): string {
    if (!tone) return 'Neutral';
    
    const lowerCase = tone.toLowerCase();
    
    if (lowerCase.includes('emotional') || lowerCase.includes('heartfelt')) {
      return 'Emotional';
    }
    if (lowerCase.includes('urgent') || lowerCase.includes('aggressive')) {
      return 'Aggressive';
    }
    if (lowerCase.includes('professional') || lowerCase.includes('formal')) {
      return 'Professional';
    }
    if (lowerCase.includes('casual') || lowerCase.includes('friendly')) {
      return 'Casual';
    }
    
    return 'Neutral';
  }
}

export const recommendationService = new RecommendationService(); 