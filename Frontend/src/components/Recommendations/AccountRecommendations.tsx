import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { 
  TrendingUp, 
  Pause, 
  Lightbulb, 
  Target, 
  AlertTriangle, 
  CheckCircle, 
  Loader2,
  RefreshCcw,
  ChevronDown,
  ChevronRight,
  Zap,
  ArrowUp,
  ArrowDown
} from 'lucide-react';
import { recommendationService } from '@/services/recommendationService';
import axios from 'axios';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

interface StructuredRecommendations {
  goal: string;
  creative_improvements: CreativeRecommendation[];
  scale_opportunities: ScaleRecommendation[];
  pause_recommendations: PauseRecommendation[];
  summary: {
    total_ads_analyzed: number;
    creative_improvement_count: number;
    scale_opportunity_count: number;
    pause_recommendation_count: number;
    potential_roas_improvement: string;
  };
}

interface CreativeRecommendation {
  ad_id: string;
  ad_name: string;
  current_performance: {
    roas: number;
    ctr: number;
    conversion_rate: number;
    spend: number;
  };
  current_creative: {
    hook: string;
    tone: string;
    power_phrases: string[];
    visual_style: string;
    cta_type: string;
  };
  recommended_creative: {
    hook: string;
    tone: string;
    power_phrases: string[];
    visual_style: string;
    cta: string;
    reasoning: string;
  };
  expected_improvement: {
    roas_increase: string;
    ctr_increase: string;
    reasoning: string;
  };
  implementation_priority: string;
}

interface ScaleRecommendation {
  ad_id: string;
  ad_name: string;
  current_performance: {
    roas: number;
    daily_spend: number;
    daily_revenue: number;
  };
  scaling_recommendation: {
    scale_percentage: string;
    new_daily_spend: string;
    projected_daily_revenue: string;
    additional_daily_profit: string;
  };
  reasoning: string;
  risk_level: string;
  monitoring_period: string;
}

interface PauseRecommendation {
  ad_id: string;
  ad_name: string;
  current_performance: {
    roas: number;
    ctr: number;
    conversion_rate: number;
    total_spend: number;
    total_revenue: number;
  };
  pause_reasons: string[];
  primary_issue: string;
  financial_impact: {
    daily_spend: string;
    daily_loss: string;
    potential_monthly_savings: string;
  };
  account_impact: string;
  urgency: string;
}

interface AccountRecommendationsProps {
  startDate: string;
  endDate: string;
  mlRecommendations?: StructuredRecommendations | null;
  skipAutoFetch?: boolean;
}

// Helper function to convert old AdRecommendation[] format to StructuredRecommendations
const convertAdRecommendationsToStructured = (adRecommendations: any[]): StructuredRecommendations => {
  // For now, return a minimal structure to prevent crashes
  // This is a fallback for the old endpoint
  return {
    goal: "ROAS Improvement Analysis (Legacy Format)",
    creative_improvements: [],
    scale_opportunities: [],
    pause_recommendations: [],
    summary: {
      total_ads_analyzed: adRecommendations.length,
      creative_improvement_count: 0,
      scale_opportunity_count: 0,
      pause_recommendation_count: 0,
      potential_roas_improvement: "N/A (Please use ML Recommendations)"
    }
  };
};

const AccountRecommendations: React.FC<AccountRecommendationsProps> = ({ 
  startDate, 
  endDate, 
  mlRecommendations = null,
  skipAutoFetch = false 
}) => {
  const [recommendations, setRecommendations] = useState<StructuredRecommendations | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingFromFacebook, setIsFetchingFromFacebook] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const fetchROASRecommendations = async (forceRefresh: boolean = false) => {
    setIsLoading(true);
    setError(null);
    
    try {
      // First, ensure we have fresh ad metrics data from Facebook
      if (forceRefresh) {
        setIsFetchingFromFacebook(true);
        await fetchAdMetricsFromFacebook();
      }
      
      // Generate ROAS-focused recommendations
      const response = await recommendationService.generateRecommendations({
        goal: {
          metric: 'roas',
          target_improvement: 10, // 10% ROAS improvement target
          timeframe_days: 30
        },
        force_refresh: forceRefresh,
        include_predictions: true
      });

      // Handle different response formats
      if (Array.isArray(response)) {
        // Old format: AdRecommendation[]
        console.log('Received old format AdRecommendation[], converting to StructuredRecommendations');
        setRecommendations(convertAdRecommendationsToStructured(response));
      } else {
        // New format: StructuredRecommendations
        console.log('Received new format StructuredRecommendations');
        setRecommendations(response);
      }
      
    } catch (err: any) {
      setError(err.message || 'Failed to fetch ROAS recommendations');
      toast({
        title: "Error",
        description: "Failed to load ROAS improvement recommendations",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
      setIsFetchingFromFacebook(false);
    }
  };

  const fetchAdMetricsFromFacebook = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication token missing');
      }

      console.log(`Fetching fresh ad metrics from Facebook for ROAS analysis: ${startDate} to ${endDate}`);
      
      const response = await axios.get('/api/v1/ad-metrics/dashboard/', {
        params: {
          start_date: startDate,
          end_date: endDate,
          force_refresh: true
        },
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      if (response.status === 200 && response.data.refresh_status?.metrics_fetched) {
        console.log('Fresh ad metrics data fetched for ROAS analysis');
        toast({
          title: "Data Refreshed",
          description: "Fresh ad performance data has been fetched for ROAS analysis.",
          variant: "default",
        });
      }
    } catch (error: any) {
      console.error('Error fetching fresh ad metrics:', error);
      toast({
        title: "Refresh Warning",
        description: "Using existing data. Fresh data fetch encountered issues.",
        variant: "default",
      });
    }
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId]
    }));
  };

  // Handle ML recommendations from background jobs
  useEffect(() => {
    console.log('AccountRecommendations useEffect triggered:', {
      mlRecommendations: !!mlRecommendations,
      skipAutoFetch,
      startDate,
      endDate
    });
    
    if (mlRecommendations) {
      // Use provided ML recommendations from background job
      console.log('Using provided ML recommendations from background job');
      setRecommendations(mlRecommendations);
      setIsLoading(false);
      setError(null);
      return;
    }
    
    // Only auto-fetch if explicitly allowed and no ML recommendations provided
    if (startDate && endDate && !skipAutoFetch && !mlRecommendations) {
      console.log('Auto-fetching recommendations via old endpoint - this should not happen when using background jobs!');
      fetchROASRecommendations(false);
    } else {
      console.log('Skipping auto-fetch:', { skipAutoFetch, hasMLRecommendations: !!mlRecommendations });
    }
  }, [startDate, endDate, mlRecommendations, skipAutoFetch]);

  const getPriorityColor = (priority: string) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'bg-red-100 text-red-800 border-red-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency?.toLowerCase()) {
      case 'high': return 'bg-red-500 text-white';
      case 'medium': return 'bg-orange-500 text-white';
      case 'low': return 'bg-green-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary mr-3" />
          <span className="text-lg">
            {isFetchingFromFacebook ? 'Fetching fresh data from Facebook...' : 'Analyzing your ads for ROAS improvements...'}
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="h-12 w-12 text-red-500 mb-4" />
          <p className="text-lg font-medium mb-2">Failed to Load ROAS Recommendations</p>
          <p className="text-muted-foreground mb-4">{error}</p>
          <div className="space-x-2">
            <Button onClick={() => fetchROASRecommendations(false)} variant="outline">
              <RefreshCcw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
            <Button onClick={() => fetchROASRecommendations(true)} variant="default">
              <RefreshCcw className="h-4 w-4 mr-2" />
              Fetch Fresh Data
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!recommendations) {
    if (skipAutoFetch && !mlRecommendations) {
      // If we're supposed to skip auto-fetch but no ML recommendations provided, 
      // show a message instead of empty screen
      return (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Target className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium mb-2">No Recommendations Available</p>
            <p className="text-muted-foreground text-center">
              Generate new ML recommendations to see optimization suggestions for your ads.
            </p>
          </CardContent>
        </Card>
      );
    }
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center">
            <Target className="h-6 w-6 mr-2 text-primary" />
            {recommendations.goal}
          </h2>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Target className="h-8 w-8 text-primary mr-3" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Ads Analyzed</p>
                <p className="text-2xl font-bold">{recommendations.summary?.total_ads_analyzed || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Lightbulb className="h-8 w-8 text-blue-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Creative Improvements</p>
                <p className="text-2xl font-bold">{recommendations.summary?.creative_improvement_count || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <TrendingUp className="h-8 w-8 text-green-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Scale Opportunities</p>
                <p className="text-2xl font-bold">{recommendations.summary?.scale_opportunity_count || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Pause className="h-8 w-8 text-red-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Pause Recommendations</p>
                <p className="text-2xl font-bold">{recommendations.summary?.pause_recommendation_count || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Zap className="h-8 w-8 text-purple-500 mr-3" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Potential ROAS Boost</p>
                <p className="text-2xl font-bold text-green-600">{recommendations.summary?.potential_roas_improvement || 'N/A'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recommendations Sections */}
      <div className="space-y-4">
        
        {/* Creative Improvements Section */}
        {recommendations.creative_improvements && recommendations.creative_improvements.length > 0 && (
          <Card className="border-l-4 border-l-blue-500">
            <Collapsible
              open={expandedSections['creative']}
              onOpenChange={() => toggleSection('creative')}
            >
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Lightbulb className="h-6 w-6 text-blue-500" />
                      <div>
                        <CardTitle className="text-xl">Increase CTR through Better Creatives</CardTitle>
                        <CardDescription>
                          {recommendations.creative_improvements.length} ads need creative improvements to boost engagement and conversions
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant="secondary">{recommendations.creative_improvements.length} ads</Badge>
                      {expandedSections['creative'] ? (
                        <ChevronDown className="h-5 w-5" />
                      ) : (
                        <ChevronRight className="h-5 w-5" />
                      )}
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>
              
              <CollapsibleContent>
                <CardContent className="space-y-4">
                  {recommendations.creative_improvements.map((ad, index) => (
                    <div key={ad.ad_id} className="bg-blue-50 p-4 rounded-lg space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="font-semibold text-lg">{ad.ad_name}</h4>
                        <Badge className={getPriorityColor(ad.implementation_priority)}>
                          {ad.implementation_priority} Priority
                        </Badge>
                      </div>
                      
                      {/* Current Performance */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-white p-3 rounded-md">
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Current ROAS</p>
                          <p className="text-lg font-bold">{ad.current_performance?.roas || 'N/A'}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Current CTR</p>
                          <p className="text-lg font-bold">{ad.current_performance?.ctr || 'N/A'}%</p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Conv. Rate</p>
                          <p className="text-lg font-bold">{ad.current_performance?.conversion_rate || 'N/A'}%</p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Total Spend</p>
                          <p className="text-lg font-bold">${ad.current_performance?.spend || 'N/A'}</p>
                        </div>
                      </div>

                      {/* Creative Comparison */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Current Creative */}
                        <div className="bg-white p-4 rounded-md border border-red-200">
                          <h5 className="font-medium text-red-700 mb-3 flex items-center">
                            <ArrowDown className="h-4 w-4 mr-1" />
                            Current Creative (Underperforming)
                          </h5>
                          <div className="space-y-2 text-sm">
                            <div><strong>Hook:</strong> {ad.current_creative?.hook || 'N/A'}</div>
                            <div><strong>Tone:</strong> {ad.current_creative?.tone || 'N/A'}</div>
                            <div><strong>Power Phrases:</strong> {Array.isArray(ad.current_creative?.power_phrases) ? ad.current_creative.power_phrases.join(', ') : 'None'}</div>
                            <div><strong>Visual Style:</strong> {ad.current_creative?.visual_style || 'N/A'}</div>
                            <div><strong>Call to Action:</strong> {ad.current_creative?.cta_type || 'N/A'}</div>
                          </div>
                        </div>

                        {/* Recommended Creative */}
                        <div className="bg-white p-4 rounded-md border border-green-200">
                          <h5 className="font-medium text-green-700 mb-3 flex items-center">
                            <ArrowUp className="h-4 w-4 mr-1" />
                            Recommended Creative (AI + Top Performers)
                          </h5>
                          <div className="space-y-2 text-sm">
                            <div><strong>Hook:</strong> {ad.recommended_creative?.hook || 'N/A'}</div>
                            <div><strong>Tone:</strong> {ad.recommended_creative?.tone || 'N/A'}</div>
                            <div><strong>Power Phrases:</strong> {Array.isArray(ad.recommended_creative?.power_phrases) ? ad.recommended_creative.power_phrases.join(', ') : 'None'}</div>
                            <div><strong>Visual Style:</strong> {ad.recommended_creative?.visual_style || 'N/A'}</div>
                            <div><strong>Call to Action:</strong> {ad.recommended_creative?.cta || 'N/A'}</div>
                          </div>
                        </div>
                      </div>

                      {/* Expected Improvement */}
                      <div className="bg-green-50 p-3 rounded-md">
                        <h5 className="font-medium text-green-800 mb-2">Expected Improvement</h5>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="font-medium">ROAS Increase:</span> {ad.expected_improvement?.roas_increase || 'N/A'}
                          </div>
                          <div>
                            <span className="font-medium">CTR Increase:</span> {ad.expected_improvement?.ctr_increase || 'N/A'}
                          </div>
                        </div>
                        <p className="text-xs text-green-700 mt-2">{ad.expected_improvement?.reasoning || 'N/A'}</p>
                        <p className="text-xs text-green-700 mt-1">AI Reasoning: {ad.recommended_creative?.reasoning || 'N/A'}</p>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}

        {/* Scale Opportunities Section */}
        {recommendations.scale_opportunities && recommendations.scale_opportunities.length > 0 && (
          <Card className="border-l-4 border-l-green-500">
            <Collapsible
              open={expandedSections['scale']}
              onOpenChange={() => toggleSection('scale')}
            >
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <TrendingUp className="h-6 w-6 text-green-500" />
                      <div>
                        <CardTitle className="text-xl">Scale High-Performing Ads</CardTitle>
                        <CardDescription>
                          {recommendations.scale_opportunities.length} ads with strong ROAS ready for budget increases
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant="secondary">{recommendations.scale_opportunities.length} ads</Badge>
                      {expandedSections['scale'] ? (
                        <ChevronDown className="h-5 w-5" />
                      ) : (
                        <ChevronRight className="h-5 w-5" />
                      )}
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>
              
              <CollapsibleContent>
                <CardContent className="space-y-4">
                  {recommendations.scale_opportunities.map((ad, index) => (
                    <div key={ad.ad_id} className="bg-green-50 p-4 rounded-lg space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="font-semibold text-lg">{ad.ad_name}</h4>
                        <Badge className={`${ad.risk_level === 'Low' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                          {ad.risk_level} Risk
                        </Badge>
                      </div>

                      {/* Current vs Projected Performance */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-white p-4 rounded-md">
                          <h5 className="font-medium text-gray-700 mb-3">Current Performance</h5>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span>ROAS:</span>
                              <span className="font-bold">{ad.current_performance.roas}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Daily Spend:</span>
                              <span className="font-bold">${ad.current_performance.daily_spend}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Daily Revenue:</span>
                              <span className="font-bold">${ad.current_performance.daily_revenue}</span>
                            </div>
                          </div>
                        </div>

                        <div className="bg-white p-4 rounded-md border border-green-200">
                          <h5 className="font-medium text-green-700 mb-3">Scaling Recommendation</h5>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span>Scale by:</span>
                              <span className="font-bold text-green-600">{ad.scaling_recommendation.scale_percentage}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>New Daily Spend:</span>
                              <span className="font-bold">{ad.scaling_recommendation.new_daily_spend}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Projected Revenue:</span>
                              <span className="font-bold">{ad.scaling_recommendation.projected_daily_revenue}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Additional Profit:</span>
                              <span className="font-bold text-green-600">{ad.scaling_recommendation.additional_daily_profit}</span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Reasoning & Monitoring */}
                      <div className="bg-white p-3 rounded-md">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <h6 className="font-medium text-gray-700 mb-1">Why Scale This Ad:</h6>
                            <p className="text-sm text-gray-600">{ad.reasoning}</p>
                          </div>
                          <div>
                            <h6 className="font-medium text-gray-700 mb-1">Monitoring Period:</h6>
                            <p className="text-sm text-gray-600">{ad.monitoring_period}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}

        {/* Pause Recommendations Section */}
        {recommendations.pause_recommendations && recommendations.pause_recommendations.length > 0 && (
          <Card className="border-l-4 border-l-red-500">
            <Collapsible
              open={expandedSections['pause']}
              onOpenChange={() => toggleSection('pause')}
            >
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-muted/50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Pause className="h-6 w-6 text-red-500" />
                      <div>
                        <CardTitle className="text-xl">Pause Underperforming Ads</CardTitle>
                        <CardDescription>
                          {recommendations.pause_recommendations.length} ads dragging down account performance and wasting budget
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant="secondary">{recommendations.pause_recommendations.length} ads</Badge>
                      {expandedSections['pause'] ? (
                        <ChevronDown className="h-5 w-5" />
                      ) : (
                        <ChevronRight className="h-5 w-5" />
                      )}
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>
              
              <CollapsibleContent>
                <CardContent className="space-y-4">
                  {recommendations.pause_recommendations.map((ad, index) => (
                    <div key={ad.ad_id} className="bg-red-50 p-4 rounded-lg space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="font-semibold text-lg">{ad.ad_name}</h4>
                        <Badge className={getUrgencyColor(ad.urgency)}>
                          {ad.urgency} Urgency
                        </Badge>
                      </div>

                      {/* Performance Summary */}
                      <div className="bg-white p-4 rounded-md border border-red-200">
                        <h5 className="font-medium text-red-700 mb-3">Poor Performance Metrics</h5>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">ROAS</p>
                            <p className="text-lg font-bold text-red-600">{ad.current_performance.roas}</p>
                          </div>
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">CTR</p>
                            <p className="text-lg font-bold text-red-600">{ad.current_performance.ctr}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">Conv. Rate</p>
                            <p className="text-lg font-bold text-red-600">{ad.current_performance.conversion_rate}%</p>
                          </div>
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">Spend</p>
                            <p className="text-lg font-bold">${ad.current_performance.total_spend}</p>
                          </div>
                          <div className="text-center">
                            <p className="text-sm text-muted-foreground">Revenue</p>
                            <p className="text-lg font-bold">${ad.current_performance.total_revenue}</p>
                          </div>
                        </div>
                      </div>

                      {/* Pause Reasons */}
                      <div className="bg-white p-4 rounded-md">
                        <h5 className="font-medium text-gray-700 mb-3">Reasons to Pause</h5>
                        <div className="space-y-2">
                          <div className="bg-red-100 p-2 rounded text-sm">
                            <strong>Primary Issue:</strong> {ad.primary_issue}
                          </div>
                          {(ad.pause_reasons || []).map((reason, idx) => (
                            <div key={idx} className="text-sm text-gray-600">• {reason}</div>
                          ))}
                        </div>
                      </div>

                      {/* Financial Impact */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-white p-4 rounded-md">
                          <h5 className="font-medium text-gray-700 mb-3">Financial Impact</h5>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span>Daily Spend:</span>
                              <span>{ad.financial_impact.daily_spend}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Daily Loss:</span>
                              <span className="text-red-600 font-bold">{ad.financial_impact.daily_loss}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Monthly Savings:</span>
                              <span className="text-green-600 font-bold">{ad.financial_impact.potential_monthly_savings}</span>
                            </div>
                          </div>
                        </div>

                        <div className="bg-white p-4 rounded-md">
                          <h5 className="font-medium text-gray-700 mb-3">Account Impact</h5>
                          <p className="text-sm text-gray-600">{ad.account_impact}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}

        {/* No Recommendations */}
        {(!recommendations.creative_improvements || recommendations.creative_improvements.length === 0) && 
         (!recommendations.scale_opportunities || recommendations.scale_opportunities.length === 0) && 
         (!recommendations.pause_recommendations || recommendations.pause_recommendations.length === 0) && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <CheckCircle className="h-12 w-12 text-green-500 mb-4" />
              <p className="text-lg font-medium mb-2">Excellent Account Performance!</p>
              <p className="text-muted-foreground text-center">
                Your ads are performing well. No critical ROAS improvements needed at this time.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default AccountRecommendations; 