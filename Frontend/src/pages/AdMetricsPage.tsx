import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlotlyLineChart } from '@/components/ui/plotly-chart';
import { Button } from '@/components/ui/button';
import { Loader2, RefreshCcw } from 'lucide-react';
import { addDays, format, subDays } from 'date-fns';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { AdMetricsByAdResponse } from '@/types/adMetrics';

// Types for API response
interface AdMetric {
  date: string;
  ad_id: string;
  ad_name: string;
  spend: number;
  revenue: number;
  clicks: number;
  impressions: number;
  purchases: number;
  ctr: number;
  cpc: number;
  cpm: number;
  roas: number;
}

interface UniqueAd {
  ad_id: string;
  ad_name: string;
}

interface ApiResponse {
  ad_metrics: AdMetric[];
  unique_ads: UniqueAd[];
  date_range: {
    start_date: string;
    end_date: string;
  };
}

interface DateRange {
  from: Date;
  to: Date;
}

// Available metrics to display
const METRICS = [
  { id: 'roas', name: 'ROAS (Return on Ad Spend)', format: (val: number) => `${val.toFixed(2)}x` },
  { id: 'ctr', name: 'CTR (Click-Through Rate)', format: (val: number) => `${(val).toFixed(2)}%` },
  { id: 'cpc', name: 'CPC (Cost Per Click)', format: (val: number) => `Rs.${val.toFixed(2)}` },
  { id: 'cpm', name: 'CPM (Cost Per 1000 Impressions)', format: (val: number) => `Rs.${val.toFixed(2)}` },
  { id: 'purchases', name: 'Conversion Volume', format: (val: number) => val.toFixed(0) },
];

const AdMetricsPage = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState<AdMetricsByAdResponse | null>(null);
  const [selectedAds, setSelectedAds] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState<string>('last7Days');
  const [dateRange, setDateRange] = useState<DateRange>({
    from: subDays(new Date(), 7),
    to: new Date()
  });
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [selectedMetric, setSelectedMetric] = useState<string>('roas');
  const [useOnlyAnalyzedAds, setUseOnlyAnalyzedAds] = useState<boolean>(true);

  // Handle time range selection
  const handleTimeRangeChange = (value: string) => {
    setTimeRange(value);
    
    let newRange: DateRange;
    const today = new Date();
    
    switch (value) {
      case 'today':
        newRange = { from: today, to: today };
        break;
      case 'last7Days':
        newRange = { from: subDays(today, 7), to: today };
        break;
      case 'last30Days':
        newRange = { from: subDays(today, 30), to: today };
        break;
      default:
        return; // For custom range, don't update dates
    }
    
    setDateRange(newRange);
  };

  // Create a wrapper function to handle DateRangePicker onChange
  const handleDateRangePickerChange = (range: any) => {
    if (range && range.from) {
      const newRange: DateRange = {
        from: range.from,
        to: range.to || range.from
      };
      setDateRange(newRange);
      setTimeRange('custom');
    }
  };

  // Function to toggle selection of an ad
  const toggleAdSelection = (adId: string) => {
    setSelectedAds((prev) => {
      if (prev.includes(adId)) {
        return prev.filter(id => id !== adId);
      } else {
        return [...prev, adId];
      }
    });
  };

  // Function to select all ads
  const selectAllAds = () => {
    if (metrics?.unique_ads) {
      setSelectedAds(metrics.unique_ads.map(ad => ad.ad_id));
    }
  };

  // Function to deselect all ads
  const deselectAllAds = () => {
    setSelectedAds([]);
  };

  // Fetch metrics data from API
  const fetchMetrics = async () => {
    if (!user) return;
    
    setIsLoading(true);
    
    try {
      // Format dates for API
      const startDate = format(dateRange.from || new Date(), 'yyyy-MM-dd');
      const endDate = format(dateRange.to || new Date(), 'yyyy-MM-dd');
      
      console.log(`Fetching ad metrics from ${startDate} to ${endDate}, force_refresh: ${forceRefresh}, use_only_analyzed_ads: ${useOnlyAnalyzedAds}`);
      
      // Call API - use the right endpoint path
      const response = await axios.get('/api/v1/ad-metrics/by-ad/', {
        params: {
          start_date: startDate,
          end_date: endDate,
          force_refresh: forceRefresh,
          use_only_analyzed_ads: useOnlyAnalyzedAds
        },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        },
        timeout: 60000 // 60 seconds timeout for Facebook data fetching
      });
      
      console.log('Response received:', response.data);
      
      // Set data
      setMetrics(response.data);
      
      // Initialize selected ads if none selected yet
      if (selectedAds.length === 0 && response.data.unique_ads.length > 0) {
        // Default to selecting first 5 ads or all if less than 5
        const adsToSelect = response.data.unique_ads.slice(0, Math.min(5, response.data.unique_ads.length));
        setSelectedAds(adsToSelect.map(ad => ad.ad_id));
      }
      
      toast({
        title: "Data loaded",
        description: `Loaded data for ${response.data.unique_ads.length} ads`,
        variant: "default",
      });
    } catch (err) {
      console.error('Error fetching ad metrics:', err);
      
      toast({
        title: "Error loading data",
        description: "There was a problem loading your ad metrics. Please try again later.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
      setForceRefresh(false); // Reset force refresh
    }
  };

  // Fetch metrics when date range changes
  useEffect(() => {
    fetchMetrics();
  }, [dateRange, user, forceRefresh, useOnlyAnalyzedAds]);

  // Prepare data for the selected metric
  const prepareChartData = () => {
    if (!metrics || !metrics.ad_metrics || metrics.ad_metrics.length === 0 || selectedAds.length === 0) {
      return [];
    }

    // Filter metrics for selected ads
    const filteredMetrics = metrics.ad_metrics.filter(metric => selectedAds.includes(metric.ad_id));
    
    // Group by ad
    const metricsByAd: Record<string, AdMetric[]> = {};
    for (const metric of filteredMetrics) {
      if (!metricsByAd[metric.ad_id]) {
        metricsByAd[metric.ad_id] = [];
      }
      metricsByAd[metric.ad_id].push(metric);
    }
    
    // Sort each ad's metrics by date
    Object.values(metricsByAd).forEach(adMetrics => {
      adMetrics.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    });
    
    // Create a trace for each ad
    return Object.entries(metricsByAd).map(([adId, adMetrics]) => {
      const adName = adMetrics[0]?.ad_name || adId;
      return {
        x: adMetrics.map(m => format(new Date(m.date), 'MMM dd')),
        y: adMetrics.map(m => {
          const value = m[selectedMetric as keyof AdMetric];
          // Multiply CTR by 100 to show as percentage
          return selectedMetric === 'ctr' ? (value as number) * 100 : value;
        }),
        type: 'scatter',
        mode: 'lines+markers',
        name: adName,
      };
    });
  };

  // Get the appropriate y-axis title based on selected metric
  const getYAxisTitle = () => {
    const metric = METRICS.find(m => m.id === selectedMetric);
    if (!metric) return '';
    
    switch (selectedMetric) {
      case 'roas':
        return 'ROAS (multiple)';
      case 'ctr':
        return 'CTR (%)';
      case 'cpc':
        return 'Cost Per Click (Rs.)';
      case 'cpm':
        return 'Cost Per 1000 Impressions (Rs.)';
      case 'purchases':
        return 'Conversion Volume (count)';
      default:
        return metric.name;
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-[calc(100vh-100px)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <span className="text-lg font-medium">
          Loading ad metrics data...
        </span>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-10 space-y-8 overflow-auto h-[calc(100vh-100px)]">
      <div className="bg-background py-4 px-8 border-b shadow-sm">
        <div className="container mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Ad Metrics</h1>
              <p className="text-muted-foreground">
                Detailed performance metrics for your ads
              </p>
            </div>
            <div className="flex items-center gap-4 w-full md:w-auto">
              <div className="flex items-center gap-3 flex-1 md:flex-none">
                <Tabs value={timeRange} onValueChange={handleTimeRangeChange} className="w-[360px]">
                  <TabsList className="grid w-full grid-cols-4 h-9">
                    <TabsTrigger value="today" className="text-xs px-1">Today</TabsTrigger>
                    <TabsTrigger value="last7Days" className="text-xs px-1">Last 7 Days</TabsTrigger>
                    <TabsTrigger value="last30Days" className="text-xs px-1">Last 30 Days</TabsTrigger>
                    <TabsTrigger value="custom" className="text-xs px-1">Custom</TabsTrigger>
                  </TabsList>
                </Tabs>
                <DateRangePicker 
                  value={dateRange}
                  onChange={handleDateRangePickerChange}
                  className="w-[220px]"
                />
              </div>
              <div className="flex items-center gap-2">
                <Label htmlFor="analyzed-ads-toggle" className="text-sm whitespace-nowrap">Only Analyzed Ads</Label>
                <Switch
                  id="analyzed-ads-toggle"
                  checked={useOnlyAnalyzedAds}
                  onCheckedChange={(checked) => {
                    console.log(`Only Analyzed Ads toggle changed to: ${checked}`);
                    setUseOnlyAnalyzedAds(checked);
                    // Trigger data refresh
                    setForceRefresh(true);
                  }}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10"
                onClick={() => {
                  setForceRefresh(true);
                }}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <RefreshCcw className="h-5 w-5" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar with ad selection */}
        <div className="w-full lg:w-1/4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Ad Selection</CardTitle>
              <CardDescription>
                Select ads to display in the chart
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex justify-between mb-2">
                <Button variant="outline" size="sm" onClick={selectAllAds}>Select All</Button>
                <Button variant="outline" size="sm" onClick={deselectAllAds}>Deselect All</Button>
              </div>
              <div className="max-h-[300px] overflow-y-auto space-y-2 border rounded-md p-2">
                {metrics?.unique_ads.map(ad => (
                  <div key={ad.ad_id} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id={`ad-${ad.ad_id}`}
                      className="h-4 w-4 rounded text-primary"
                      checked={selectedAds.includes(ad.ad_id)}
                      onChange={() => toggleAdSelection(ad.ad_id)}
                    />
                    <label htmlFor={`ad-${ad.ad_id}`} className="text-sm">
                      {ad.ad_name}
                    </label>
                  </div>
                ))}
                {(!metrics?.unique_ads || metrics.unique_ads.length === 0) && (
                  <div className="text-sm text-muted-foreground">No ads found in selected date range</div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Metric Selection</CardTitle>
              <CardDescription>
                Choose which metric to display
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="metric-select">Select Metric</Label>
                  <Select
                    value={selectedMetric}
                    onValueChange={setSelectedMetric}
                  >
                    <SelectTrigger id="metric-select">
                      <SelectValue placeholder="Select a metric" />
                    </SelectTrigger>
                    <SelectContent>
                      {METRICS.map(metric => (
                        <SelectItem key={metric.id} value={metric.id}>
                          {metric.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main content with charts */}
        <div className="w-full lg:w-3/4">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>
                {METRICS.find(m => m.id === selectedMetric)?.name || 'Metric'} by Ad
              </CardTitle>
              <CardDescription>
                Compare {METRICS.find(m => m.id === selectedMetric)?.name.toLowerCase() || 'metrics'} across different ads over time
              </CardDescription>
            </CardHeader>
            <CardContent className="h-[500px]">
              {selectedAds.length > 0 ? (
                <PlotlyLineChart 
                  data={prepareChartData()}
                  layout={{
                    yaxis: { 
                      title: getYAxisTitle() 
                    },
                    legend: {
                      orientation: 'h',
                      y: -0.2
                    },
                    margin: {
                      b: 100
                    }
                  }}
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <p className="text-muted-foreground">Please select at least one ad to display data</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default AdMetricsPage; 