import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  TrendingUp, 
  Target, 
  Lightbulb, 
  CheckCircle, 
  AlertTriangle,
  BarChart3,
  RefreshCw,
  Filter,
  Eye
} from 'lucide-react';
import { recommendationService } from '@/services/recommendationService';
import { RecommendationCard } from './RecommendationCard';
import { QuickAnalysisModal } from './QuickAnalysisModal';
import { RecommendationFilters } from './RecommendationFilters';

interface AdRecommendation {
  _id: string;
  ad_id: string;
  ad_name: string;
  performance_summary: {
    roas: number;
    ctr: number;
    cpc: number;
    spend: number;
    revenue: number;
    clicks: number;
    impressions: number;
    purchases: number;
  };
  goal: {
    metric: string;
    target_improvement: number;
    current_value: number;
    target_value: number;
  };
  fixed_recommendations: Array<{
    type: string;
    priority: number;
    title: string;
    description: string;
    expected_impact: string;
    confidence_score: number;
    implementation_effort: string;
  }>;
  ai_recommendations: Array<{
    suggestion: string;
    reasoning: string;
    confidence_score: number;
    specific_changes?: any;
  }>;
  status: string;
  generated_at: string;
}

interface GenerateRecommendationsRequest {
  ad_ids?: string[];
  goal: {
    metric: string;
    target_improvement: number;
    timeframe_days: number;
  };
  force_refresh: boolean;
  include_predictions: boolean;
}

export const RecommendationsDashboard: React.FC = () => {
  const [recommendations, setRecommendations] = useState<AdRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState('roas');
  const [targetImprovement, setTargetImprovement] = useState(10);
  const [filters, setFilters] = useState({
    status: 'active',
    priority: 'all',
    metric: 'all'
  });
  const [showQuickAnalysis, setShowQuickAnalysis] = useState(false);
  const [selectedAdId, setSelectedAdId] = useState<string>('');

  useEffect(() => {
    loadRecommendations();
  }, [filters]);

  const loadRecommendations = async () => {
    try {
      setLoading(true);
      const data = await recommendationService.getRecommendations(filters);
      setRecommendations(data);
    } catch (error) {
      console.error('Error loading recommendations:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateRecommendations = async () => {
    try {
      setGenerating(true);
      
      const request: GenerateRecommendationsRequest = {
        goal: {
          metric: selectedMetric,
          target_improvement: targetImprovement,
          timeframe_days: 30
        },
        force_refresh: true,
        include_predictions: true
      };

      const newRecommendations = await recommendationService.generateRecommendations(request);
      setRecommendations(newRecommendations);
      
      // Show success message
      alert(`Generated ${newRecommendations.length} recommendations successfully!`);
      
    } catch (error) {
      console.error('Error generating recommendations:', error);
      alert('Error generating recommendations. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const updateRecommendationStatus = async (id: string, status: string, notes?: string) => {
    try {
      await recommendationService.updateStatus(id, status, notes);
      await loadRecommendations(); // Refresh the list
    } catch (error) {
      console.error('Error updating recommendation status:', error);
    }
  };

  const getPerformanceColor = (metric: string, value: number) => {
    switch (metric) {
      case 'roas':
        if (value >= 3) return 'text-green-600';
        if (value >= 2) return 'text-yellow-600';
        return 'text-red-600';
      case 'ctr':
        if (value >= 0.02) return 'text-green-600';
        if (value >= 0.01) return 'text-yellow-600';
        return 'text-red-600';
      case 'cpc':
        if (value <= 2) return 'text-green-600';
        if (value <= 5) return 'text-yellow-600';
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getSummaryStats = () => {
    const totalAds = recommendations.length;
    const criticalIssues = recommendations.filter(r => 
      r.fixed_recommendations.some(fr => fr.priority === 1)
    ).length;
    const avgImprovement = recommendations.reduce((sum, r) => 
      sum + r.goal.target_improvement, 0
    ) / Math.max(totalAds, 1);
    const implemented = recommendations.filter(r => r.status === 'implemented').length;

    return { totalAds, criticalIssues, avgImprovement, implemented };
  };

  const stats = getSummaryStats();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center space-x-2">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Loading recommendations...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Ad Performance Recommendations</h1>
          <p className="text-gray-600 mt-2">
            AI-powered insights to improve your ad performance
          </p>
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={() => setShowQuickAnalysis(true)}
          >
            <Eye className="h-4 w-4 mr-2" />
            Quick Analysis
          </Button>
          <Button 
            onClick={generateRecommendations}
            disabled={generating}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {generating ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <TrendingUp className="h-4 w-4 mr-2" />
                Generate Recommendations
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Ads Analyzed</p>
                <p className="text-2xl font-bold">{stats.totalAds}</p>
              </div>
              <BarChart3 className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Critical Issues</p>
                <p className="text-2xl font-bold text-red-600">{stats.criticalIssues}</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-red-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Avg Target Improvement</p>
                <p className="text-2xl font-bold text-green-600">{stats.avgImprovement.toFixed(1)}%</p>
              </div>
              <Target className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Implemented</p>
                <p className="text-2xl font-bold text-purple-600">{stats.implemented}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Generation Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Lightbulb className="h-5 w-5 mr-2" />
            Generate New Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Target Metric</label>
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="w-full p-2 border rounded-md"
              >
                <option value="roas">ROAS (Return on Ad Spend)</option>
                <option value="ctr">CTR (Click Through Rate)</option>
                <option value="cpc">CPC (Cost Per Click)</option>
                <option value="conversion_rate">Conversion Rate</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Target Improvement (%)</label>
              <input
                type="number"
                value={targetImprovement}
                onChange={(e) => setTargetImprovement(Number(e.target.value))}
                min="1"
                max="100"
                className="w-full p-2 border rounded-md"
              />
            </div>
            <div className="flex items-end">
              <Button 
                onClick={generateRecommendations}
                disabled={generating}
                className="w-full"
              >
                {generating ? 'Generating...' : 'Generate'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <RecommendationFilters
        filters={filters}
        onFiltersChange={setFilters}
      />

      {/* Recommendations List */}
      <div className="space-y-4">
        {recommendations.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center">
              <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                No recommendations found
              </h3>
              <p className="text-gray-600 mb-4">
                Generate your first set of recommendations to get started with optimizing your ad performance.
              </p>
              <Button onClick={generateRecommendations} disabled={generating}>
                <TrendingUp className="h-4 w-4 mr-2" />
                Generate Recommendations
              </Button>
            </CardContent>
          </Card>
        ) : (
          recommendations.map((recommendation) => (
            <RecommendationCard
              key={recommendation._id}
              recommendation={recommendation}
              onStatusUpdate={updateRecommendationStatus}
              onViewDetails={(adId) => {
                setSelectedAdId(adId);
                setShowQuickAnalysis(true);
              }}
            />
          ))
        )}
      </div>

      {/* Quick Analysis Modal */}
      {showQuickAnalysis && (
        <QuickAnalysisModal
          adId={selectedAdId}
          isOpen={showQuickAnalysis}
          onClose={() => {
            setShowQuickAnalysis(false);
            setSelectedAdId('');
          }}
          metric={selectedMetric}
          targetImprovement={targetImprovement}
        />
      )}
    </div>
  );
}; 