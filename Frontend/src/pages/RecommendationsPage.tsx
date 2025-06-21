import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/components/ui/use-toast';
import { Separator } from '@/components/ui/separator';
import { 
  TrendingUp, 
  Target, 
  Lightbulb, 
  RefreshCw,
  Brain,
  Zap,
  CheckCircle,
  Clock,
  AlertTriangle,
  Loader2,
  Calendar,
  DollarSign,
  Users,
  Eye,
  ShoppingCart,
  Info,
  TrendingDown,
  BarChart3
} from 'lucide-react';
import AccountRecommendations from '@/components/Recommendations/AccountRecommendations';
import { format } from 'date-fns';

// Create a simple service class to fix the import issue
class RecommendationService {
  async getAllStoredRecommendations(): Promise<any[]> {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/recommendations/stored-history', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error('Failed to fetch stored recommendations');
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching stored recommendations:', error);
      throw error;
    }
  }
}

interface RecommendationJob {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  total_steps: number;
  step_name: string;
  started_at: string;
  completed_at?: string;
  error?: string;
  result?: any;
}

interface AdRecommendation {
  ad_id: string;
  ad_name: string;
  expected_roas_improvement: string;
  account_level_roas_impact: string;
  current_roas?: number;
  predicted_roas?: number;
  optimization_goal?: string;
  // Strategy-specific fields
  ai_optimized_creative?: { 
    hook?: string;
    tone?: string;
    visual?: string;
    reasoning?: string;
  };
  optimization_strategies?: string | string[];
  conversion_strategies?: string | string[];
  implementation_strategy?: string[];
  spend_ai_suggestion?: string;
  efficiency_ai_suggestion?: string;
  conversion_ai_suggestion?: string;
  ctr_ai_suggestion?: string;
  // Additional strategy fields
  action?: string;
  current_daily_spend?: string;
  recommended_daily_spend?: string;
  increase_percentage?: string;
  decrease_percentage?: string;
  reasoning?: string;
  optimization_metric?: string;
  current_value?: string;
  target_value?: string;
  improvement_needed?: string;
  current_conversions?: number;
  target_conversions?: number;
}

interface OptimizationSummary {
  total_ads_analyzed: number;
  successful_optimizations: number;
  total_account_roas_impact: number;
  average_predicted_improvement: number;
  max_improvement_achieved: number;
  min_improvement_achieved: number;
  ctr_improvement_opportunities: number;
  spend_optimization_opportunities: number;
  efficiency_improvement_opportunities: number;
  conversion_improvement_opportunities: number;
}

const recommendationService = new RecommendationService();

const RecommendationsPage: React.FC = () => {
  const [currentJob, setCurrentJob] = useState<RecommendationJob | null>(null);
  const [storedRecommendations, setStoredRecommendations] = useState<any[]>([]);
  const [groupedRecommendations, setGroupedRecommendations] = useState<Record<string, Record<string, AdRecommendation[]>>>({});
  const [optimizationSummaries, setOptimizationSummaries] = useState<Record<string, OptimizationSummary>>({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [errorCount, setErrorCount] = useState(0);
  const [dateRange, setDateRange] = useState({
    from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
    to: new Date()
  });
  const { toast } = useToast();

  // Load stored recommendations on component mount
  useEffect(() => {
    loadStoredRecommendations();
    
    // Also check for any running jobs
    const savedJobId = localStorage.getItem('recommendationJobId');
    const savedJobData = localStorage.getItem('recommendationJobData');
    
    if (savedJobId && savedJobData) {
      try {
        const jobData = JSON.parse(savedJobData);
        
        // Only restore if job is still running
        const startedAt = new Date(jobData.started_at);
        const now = new Date();
        const timeDiff = now.getTime() - startedAt.getTime();
        const oneHour = 60 * 60 * 1000;
        
        if (timeDiff < oneHour && (jobData.status === 'running' || jobData.status === 'pending')) {
          setCurrentJob({ ...jobData, id: savedJobId });
          setIsGenerating(true);
          checkJobStatus(savedJobId);
        } else {
          // Clean up old job data
          localStorage.removeItem('recommendationJobId');
          localStorage.removeItem('recommendationJobData');
        }
      } catch (error) {
        console.error('Error restoring job data:', error);
        localStorage.removeItem('recommendationJobId');
        localStorage.removeItem('recommendationJobData');
      }
    }
  }, []);

  const loadStoredRecommendations = async () => {
    try {
      setIsLoading(true);
      const recommendations = await recommendationService.getAllStoredRecommendations();
      setStoredRecommendations(recommendations);
      
      if (recommendations.length > 0) {
        // Group recommendations by date and then by strategy
        const { grouped, summaries } = groupRecommendationsByDateAndStrategy(recommendations);
        setGroupedRecommendations(grouped);
        setOptimizationSummaries(summaries);
      }
    } catch (error) {
      console.error('Error loading stored recommendations:', error);
      // Don't show error toast here - let user generate new recommendations
    } finally {
      setIsLoading(false);
    }
  };

  const groupRecommendationsByDateAndStrategy = (recommendations: any[]): { 
    grouped: Record<string, Record<string, AdRecommendation[]>>, 
    summaries: Record<string, OptimizationSummary> 
  } => {
    const grouped: Record<string, Record<string, AdRecommendation[]>> = {};
    const summaries: Record<string, OptimizationSummary> = {};
    
    recommendations.forEach(batch => {
      const date = new Date(batch.generated_at).toISOString().split('T')[0];
      
      if (!grouped[date]) {
        grouped[date] = {
          ctr_improvements: [],
          spend_optimizations: [],
          efficiency_improvements: [],
          conversion_improvements: []
        };
      }
      
      // Store optimization summary for this date
      if (batch.optimization_summary) {
        summaries[date] = batch.optimization_summary;
      }
      
      // Try multiple data access patterns to handle different storage formats
      const strategies = ['ctr_improvements', 'spend_optimizations', 'efficiency_improvements', 'conversion_improvements'];
      
      strategies.forEach(strategy => {
        let strategyData = null;
        
        // Try flattened structure first (directly on batch)
        if (batch[strategy]?.recommendations) {
          strategyData = batch[strategy];
        }
        // Try nested structure (in optimization_results)
        else if (batch.optimization_results?.[strategy]?.recommendations) {
          strategyData = batch.optimization_results[strategy];
        }
        
        if (strategyData?.recommendations && Array.isArray(strategyData.recommendations)) {
          grouped[date][strategy].push(...strategyData.recommendations);
        }
      });
    });
    
    // Sort ads within each strategy by ROAS improvement (descending)
    Object.values(grouped).forEach(dateGroup => {
      Object.values(dateGroup).forEach(ads => {
        ads.sort((a, b) => {
          const aImprovement = parseFloat(a.expected_roas_improvement?.replace('%', '') || '0');
          const bImprovement = parseFloat(b.expected_roas_improvement?.replace('%', '') || '0');
          return bImprovement - aImprovement;
        });
      });
    });
    
    return { grouped, summaries };
  };

  const getStrategyDisplayName = (strategy: string): string => {
    const names: Record<string, string> = {
      ctr_improvements: 'CTR Improvements',
      spend_optimizations: 'Spend Optimizations',
      efficiency_improvements: 'Efficiency Improvements',
      conversion_improvements: 'Conversion Improvements'
    };
    return names[strategy] || strategy;
  };

  const getStrategyIcon = (strategy: string) => {
    const icons: Record<string, React.ReactNode> = {
      ctr_improvements: <Target className="h-4 w-4" />,
      spend_optimizations: <DollarSign className="h-4 w-4" />,
      efficiency_improvements: <TrendingUp className="h-4 w-4" />,
      conversion_improvements: <ShoppingCart className="h-4 w-4" />
    };
    return icons[strategy] || <Lightbulb className="h-4 w-4" />;
  };

  const getStrategyDescription = (strategy: string): string => {
    const descriptions: Record<string, string> = {
      ctr_improvements: 'Optimize creative elements to improve click-through rates',
      spend_optimizations: 'Adjust budget allocation for maximum ROAS',
      efficiency_improvements: 'Reduce cost per click and cost per mille',
      conversion_improvements: 'Enhance conversion rates and purchase volume'
    };
    return descriptions[strategy] || '';
  };

  const renderAdStrategies = (ad: AdRecommendation, strategy: string) => {
    const strategies = [];
    
    // CTR AI Creative Optimization
    if (ad.ai_optimized_creative || ad.ctr_ai_suggestion) {
      strategies.push(
        <div key="ctr" className="bg-blue-50 p-3 rounded-md border-l-4 border-l-blue-500">
          <div className="flex items-start gap-2">
            <Brain className="h-4 w-4 text-blue-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-medium text-blue-900 mb-1">AI Creative Optimization</p>
              <p className="text-xs text-blue-800">
                {ad.ctr_ai_suggestion || 
                 ad.ai_optimized_creative?.reasoning || 
                 ad.ai_optimized_creative?.hook || 
                 'Optimize creative elements for better CTR'}
              </p>
            </div>
          </div>
        </div>
      );
    }

    // Spend Strategy
    if (ad.spend_ai_suggestion || ad.action) {
      strategies.push(
        <div key="spend" className="bg-green-50 p-3 rounded-md border-l-4 border-l-green-500">
          <div className="flex items-start gap-2">
            <DollarSign className="h-4 w-4 text-green-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-medium text-green-900 mb-1">
                Spend Strategy {ad.action && `(${ad.action})`}
              </p>
              <p className="text-xs text-green-800">
                {ad.spend_ai_suggestion || ad.reasoning || 'Optimize spend allocation'}
              </p>
              {(ad.current_daily_spend || ad.recommended_daily_spend) && (
                <div className="mt-1 text-xs text-green-700">
                  {ad.current_daily_spend} → {ad.recommended_daily_spend}
                  {ad.increase_percentage && ` (+${ad.increase_percentage})`}
                  {ad.decrease_percentage && ` (-${ad.decrease_percentage})`}
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // Efficiency Strategy
    if (ad.efficiency_ai_suggestion || ad.optimization_metric) {
      strategies.push(
        <div key="efficiency" className="bg-purple-50 p-3 rounded-md border-l-4 border-l-purple-500">
          <div className="flex items-start gap-2">
            <TrendingUp className="h-4 w-4 text-purple-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-medium text-purple-900 mb-1">
                Efficiency Optimization {ad.optimization_metric && `(${ad.optimization_metric})`}
              </p>
              <p className="text-xs text-purple-800">
                {ad.efficiency_ai_suggestion || 
                 (typeof ad.optimization_strategies === 'string' ? ad.optimization_strategies : 
                  Array.isArray(ad.optimization_strategies) ? ad.optimization_strategies[0] : 
                  'Improve cost efficiency')}
              </p>
              {(ad.current_value || ad.target_value) && (
                <div className="mt-1 text-xs text-purple-700">
                  {ad.current_value} → {ad.target_value}
                  {ad.improvement_needed && ` (${ad.improvement_needed} improvement needed)`}
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // Conversion Strategy
    if (ad.conversion_ai_suggestion || ad.conversion_strategies) {
      strategies.push(
        <div key="conversion" className="bg-orange-50 p-3 rounded-md border-l-4 border-l-orange-500">
          <div className="flex items-start gap-2">
            <ShoppingCart className="h-4 w-4 text-orange-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-medium text-orange-900 mb-1">Conversion Strategy</p>
              <p className="text-xs text-orange-800">
                {ad.conversion_ai_suggestion || 
                 (typeof ad.conversion_strategies === 'string' ? ad.conversion_strategies : 
                  Array.isArray(ad.conversion_strategies) ? ad.conversion_strategies[0] : 
                  'Optimize conversion performance')}
              </p>
              {(ad.current_conversions !== undefined || ad.target_conversions !== undefined) && (
                <div className="mt-1 text-xs text-orange-700">
                  {ad.current_conversions} → {ad.target_conversions} conversions
                  {ad.improvement_needed && ` (${ad.improvement_needed} improvement needed)`}
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // Implementation Strategy
    if (ad.implementation_strategy && ad.implementation_strategy.length > 0) {
      strategies.push(
        <div key="implementation" className="bg-gray-50 p-3 rounded-md border-l-4 border-l-gray-500">
          <div className="flex items-start gap-2">
            <Target className="h-4 w-4 text-gray-600 mt-0.5" />
            <div className="flex-1">
              <p className="text-xs font-medium text-gray-900 mb-1">Implementation Guide</p>
              <p className="text-xs text-gray-800">{ad.implementation_strategy[0]}</p>
            </div>
          </div>
        </div>
      );
    }

    return strategies;
  };

  // Job status checking functions (same as before)
  const checkJobStatus = async (jobId: string) => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        console.error('Authentication token missing during status check');
        return;
      }

      const response = await fetch(`/api/v1/recommendations/job-status/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch job status');
      }
      
      const jobStatus = await response.json();
      setCurrentJob(jobStatus);
      setErrorCount(0);
      
      localStorage.setItem('recommendationJobData', JSON.stringify(jobStatus));
      
      if (jobStatus.status === 'completed') {
        setIsGenerating(false);
        toast({
          title: "Recommendations Generated",
          description: "Your ML-powered recommendations are ready!",
          variant: "default",
        });
        // Reload stored recommendations
        loadStoredRecommendations();
      } else if (jobStatus.status === 'failed') {
        setIsGenerating(false);
        localStorage.removeItem('recommendationJobId');
        localStorage.removeItem('recommendationJobData');
        toast({
          title: "Generation Failed",
          description: jobStatus.error || "Failed to generate recommendations",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Error checking job status:', error);
      
      const newErrorCount = errorCount + 1;
      setErrorCount(newErrorCount);
      
      if (newErrorCount >= 5) {
        setIsGenerating(false);
        setCurrentJob(null);
        localStorage.removeItem('recommendationJobId');
        localStorage.removeItem('recommendationJobData');
      }
    }
  };

  useEffect(() => {
    let pollInterval: NodeJS.Timeout;
    
    if (currentJob && currentJob.status === 'running') {
      pollInterval = setInterval(async () => {
        await checkJobStatus(currentJob.id);
      }, 2000);
    }

    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [currentJob, toast]);

  const generateRecommendations = async (useMLOptimization: boolean = true) => {
    try {
      setIsGenerating(true);
      setCurrentJob(null);
      setErrorCount(0);

      localStorage.removeItem('recommendationJobId');
      localStorage.removeItem('recommendationJobData');

      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication token missing. Please login again.');
      }

      const response = await fetch('/api/v1/recommendations/generate-background', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          use_ml_optimization: useMLOptimization,
          target_improvement: 10,
          date_range: {
            from: format(dateRange.from, 'yyyy-MM-dd'),
            to: format(dateRange.to, 'yyyy-MM-dd')
          }
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start recommendation generation');
      }

      const result = await response.json();
      
      if (result.job_id) {
        const newJob: RecommendationJob = {
          id: result.job_id,
          status: 'running',
          progress: 0,
          current_step: '1',
          total_steps: 6,
          step_name: 'Initializing recommendation generation...',
          started_at: new Date().toISOString()
        };
        
        setCurrentJob(newJob);
        localStorage.setItem('recommendationJobId', result.job_id);
        localStorage.setItem('recommendationJobData', JSON.stringify(newJob));
      }

    } catch (error: any) {
      console.error('Error generating recommendations:', error);
      setIsGenerating(false);
      toast({
        title: "Error",
        description: error.message || "Failed to generate recommendations",
        variant: "destructive",
      });
    }
  };

  const getProgressPercentage = () => {
    if (!currentJob) return 0;
    return Math.round((currentJob.current_step ? 
      (parseInt(currentJob.current_step) / currentJob.total_steps) * 100 : 0));
  };

  const getStepName = (step: string) => {
    const stepNames: { [key: string]: string } = {
      '1': 'Checking historical data...',
      '2': 'Collecting fresh Facebook data...',
      '3': 'Training ML models...',
      '4': 'Optimizing ad parameters...',
      '5': 'Generating AI recommendations...',
      '6': 'Finalizing recommendations...'
    };
    return stepNames[step] || 'Processing...';
  };

  const hasStoredRecommendations = Object.keys(groupedRecommendations).length > 0;

  return (
    <div className="h-full overflow-y-auto">
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <Brain className="h-8 w-8 mr-3 text-primary" />
              AI-Powered Recommendations
            </h1>
            <p className="text-muted-foreground mt-2">
              {hasStoredRecommendations 
                ? "Your stored ML optimization recommendations grouped by date and strategy"
                : "Get intelligent ROAS optimization suggestions using machine learning and fresh Facebook data"
              }
            </p>
          </div>
          
          <div className="flex space-x-3">
            <Button
              onClick={() => generateRecommendations(false)}
              variant="outline"
              disabled={isGenerating}
            >
              <Lightbulb className="h-4 w-4 mr-2" />
              Quick Analysis
            </Button>
            <Button
              onClick={() => generateRecommendations(true)}
              disabled={isGenerating}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Generate ML Recommendations
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Progress Card - Show when generating */}
        {isGenerating && currentJob && (
          <Card className="border-primary/20 bg-gradient-to-r from-blue-50 to-purple-50">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Brain className="h-5 w-5 mr-2 text-primary" />
                Generating ML-Powered Recommendations
              </CardTitle>
              <CardDescription>
                Using advanced machine learning to optimize your ad performance
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{getStepName(currentJob.current_step)}</span>
                  <span className="text-muted-foreground">
                    Step {currentJob.current_step} of {currentJob.total_steps}
                  </span>
                </div>
                <Progress value={getProgressPercentage()} className="h-2" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Started: {new Date(currentJob.started_at).toLocaleTimeString()}</span>
                  <span>{getProgressPercentage()}% complete</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stored Recommendations Content */}
        {hasStoredRecommendations && !isLoading ? (
          <div className="space-y-6">
            {Object.entries(groupedRecommendations)
              .sort(([dateA], [dateB]) => new Date(dateB).getTime() - new Date(dateA).getTime())
              .map(([date, strategies]) => {
                const summary = optimizationSummaries[date];
                return (
                  <Card key={date} className="border-l-4 border-l-primary">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Calendar className="h-5 w-5" />
                        {format(new Date(date), 'MMMM d, yyyy')}
                      </CardTitle>
                      <CardDescription>
                        Recommendations generated on this date
                      </CardDescription>
                      
                      {/* Optimization Summary */}
                      {summary && (
                        <Card className="bg-gradient-to-r from-green-50 to-blue-50 border-green-200">
                          <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-lg">
                              <BarChart3 className="h-5 w-5 text-green-600" />
                              Optimization Summary
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                              <div className="text-center">
                                <p className="text-2xl font-bold text-green-600">
                                  {summary.total_ads_analyzed}
                                </p>
                                <p className="text-sm text-muted-foreground">Ads Analyzed</p>
                              </div>
                              <div className="text-center">
                                <p className="text-2xl font-bold text-blue-600">
                                  +{summary.total_account_roas_impact?.toFixed(2) || '0.00'}%
                                </p>
                                <p className="text-sm text-muted-foreground">Total Account ROAS Impact</p>
                              </div>
                              <div className="text-center">
                                <p className="text-2xl font-bold text-purple-600">
                                  {summary.average_predicted_improvement?.toFixed(1) || '0.0'}%
                                </p>
                                <p className="text-sm text-muted-foreground">Avg Individual ROAS Improvement</p>
                              </div>
                              <div className="text-center">
                                <p className="text-2xl font-bold text-orange-600">
                                  {summary.max_improvement_achieved?.toFixed(1) || '0.0'}%
                                </p>
                                <p className="text-sm text-muted-foreground">Max Individual Improvement</p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {Object.entries(strategies)
                        .filter(([, ads]) => ads.length > 0)
                        .map(([strategy, ads]) => (
                          <Card key={strategy} className="bg-muted/20">
                            <CardHeader>
                              <CardTitle className="flex items-center gap-2 text-lg">
                                {getStrategyIcon(strategy)}
                                {getStrategyDisplayName(strategy)}
                                <Badge variant="secondary">{ads.length} ads</Badge>
                              </CardTitle>
                              <CardDescription>
                                {getStrategyDescription(strategy)}
                              </CardDescription>
                            </CardHeader>
                            <CardContent>
                              <div className="grid gap-4">
                                {ads.map((ad, index) => (
                                  <Card key={`${ad.ad_id}-${index}`} className="hover:shadow-md transition-shadow">
                                    <CardContent className="pt-4">
                                      <div className="flex flex-col space-y-4">
                                        {/* Ad Header with ROAS Information */}
                                        <div className="flex items-center justify-between">
                                          <div className="flex-1">
                                            <h4 className="font-medium text-sm">{ad.ad_name}</h4>
                                            <div className="flex items-center gap-3 mt-1">
                                              <p className="text-xs text-muted-foreground">
                                                Individual ROAS improvement: +{ad.expected_roas_improvement}
                                              </p>
                                              <Separator orientation="vertical" className="h-4" />
                                              <p className="text-xs text-blue-600 font-medium">
                                                Account impact: +{ad.account_level_roas_impact}
                                              </p>
                                            </div>
                                          </div>
                                          <div className="flex items-center gap-2">
                                            <Badge className="bg-green-100 text-green-800">
                                              +{ad.expected_roas_improvement} ROAS
                                            </Badge>
                                            <Badge className="bg-blue-100 text-blue-800">
                                              +{ad.account_level_roas_impact} Account
                                            </Badge>
                                          </div>
                                        </div>

                                        {/* All Strategies for this Ad */}
                                        <div className="space-y-3">
                                          {renderAdStrategies(ad, strategy)}
                                        </div>
                                      </div>
                                    </CardContent>
                                  </Card>
                                ))}
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                    </CardContent>
                  </Card>
                );
              })}
          </div>
        ) : !hasStoredRecommendations && !isGenerating && !isLoading ? (
          /* Welcome State */
          <Card className="border-dashed border-2 border-muted-foreground/25">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <div className="rounded-full bg-primary/10 p-6 mb-6">
                <Brain className="h-12 w-12 text-primary" />
              </div>
              <h3 className="text-2xl font-bold mb-2">Ready to Optimize Your Ads?</h3>
              <p className="text-muted-foreground mb-8 max-w-2xl">
                Our AI-powered recommendation engine analyzes your ad performance data, 
                trains machine learning models, and generates intelligent suggestions to improve your ROAS.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-2xl mb-8">
                <div className="flex items-start space-x-3 p-4 border rounded-lg">
                  <Target className="h-6 w-6 text-blue-500 mt-1" />
                  <div>
                    <h4 className="font-semibold">ML Optimization</h4>
                    <p className="text-sm text-muted-foreground">
                      Advanced machine learning finds the best parameter combinations for maximum ROAS
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3 p-4 border rounded-lg">
                  <RefreshCw className="h-6 w-6 text-green-500 mt-1" />
                  <div>
                    <h4 className="font-semibold">Fresh Data</h4>
                    <p className="text-sm text-muted-foreground">
                      Automatically collects the latest performance data from Facebook API
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3 p-4 border rounded-lg">
                  <Lightbulb className="h-6 w-6 text-purple-500 mt-1" />
                  <div>
                    <h4 className="font-semibold">AI Creative Suggestions</h4>
                    <p className="text-sm text-muted-foreground">
                      Intelligent creative optimization based on high-performing benchmarks
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3 p-4 border rounded-lg">
                  <CheckCircle className="h-6 w-6 text-orange-500 mt-1" />
                  <div>
                    <h4 className="font-semibold">Actionable Insights</h4>
                    <p className="text-sm text-muted-foreground">
                      Specific, implementable recommendations with expected impact
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex space-x-4">
                <Button
                  onClick={() => generateRecommendations(false)}
                  variant="outline"
                  size="lg"
                >
                  <Lightbulb className="h-5 w-5 mr-2" />
                  Quick Analysis
                </Button>
                <Button
                  onClick={() => generateRecommendations(true)}
                  size="lg"
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  <Zap className="h-5 w-5 mr-2" />
                  Generate ML Recommendations
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : isLoading ? (
          <Card>
            <CardContent className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin mr-3" />
              <span>Loading recommendations...</span>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
};

export default RecommendationsPage; 