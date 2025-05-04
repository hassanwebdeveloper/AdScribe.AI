import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlotlyBarChart, PlotlyLineChart } from '@/components/ui/plotly-chart';
import { Loader2, TrendingUp, TrendingDown, DollarSign, MousePointerClick, Eye, ShoppingCart, RefreshCcw } from 'lucide-react';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { addDays, format, subDays } from 'date-fns';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

interface DateRange {
  from: Date;
  to: Date;
}

interface AdMetricsData {
  current_period: {
    start_date: string;
    end_date: string;
    roas: number;
    ctr: number;
    cpc: number;
    cpm: number;
    conversions: number;
    spend: number;
    revenue: number;
  };
  previous_period: {
    start_date: string;
    end_date: string;
    roas: number;
    ctr: number;
    cpc: number;
    cpm: number;
    conversions: number;
    spend: number;
    revenue: number;
  };
  daily_metrics: Array<{
    date: string;
    spend: number;
    revenue: number;
    clicks: number;
    impressions: number;
    purchases: number;
    ctr: number;
    roas: number;
    ad_id?: string;
    ad_name?: string;
  }>;
  refresh_status: {
    metrics_fetched: boolean;
    has_complete_data: boolean;
    force_refresh_attempted: boolean;
  };
  ad_metrics: Array<{
    date: string;
    ad_id: string;
    ad_name: string;
    campaign_name?: string;
    adset_name?: string;
    spend: number;
    revenue: number;
    clicks: number;
    impressions: number;
    purchases: number;
    ctr: number;
    cpc: number;
    cpm: number;
    roas: number;
  }>;
  unique_ads: Array<{
    ad_id: string;
    ad_name: string;
  }>;
}

const Dashboard = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isFetchingFromFacebook, setIsFetchingFromFacebook] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<AdMetricsData | null>(null);
  const [timeRange, setTimeRange] = useState<string>('last7Days');
  const [dateRange, setDateRange] = useState<DateRange>({
    from: subDays(new Date(), 7),
    to: new Date()
  });
  const [fetchAttempts, setFetchAttempts] = useState<number>(0);
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // Calculate previous date range
  const getPreviousRange = (from: Date, to: Date) => {
    const rangeInDays = Math.ceil((to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24));
    return {
      from: subDays(from, rangeInDays),
      to: subDays(from, 1)
    };
  };

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
    // Reset fetch attempts when changing date range
    setFetchAttempts(0);
  };

  // Handle custom date range selection
  const handleDateRangeChange = (range: DateRange) => {
    setDateRange(range);
    setTimeRange('custom');
    // Reset fetch attempts when changing date range
    setFetchAttempts(0);
  };

  // Create a wrapper function to handle DateRangePicker onChange with proper typing
  const handleDateRangePickerChange = (range: any) => {
    if (range && range.from) {
      const newRange: DateRange = {
        from: range.from,
        to: range.to || range.from
      };
      setDateRange(newRange);
    }
  };

  // Fetch metrics data based on date range
  const fetchMetrics = async () => {
    if (!user) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Format dates for API
      const startDate = format(dateRange.from || new Date(), 'yyyy-MM-dd');
      const endDate = format(dateRange.to || new Date(), 'yyyy-MM-dd');
      
      console.log(`Fetching metrics from ${startDate} to ${endDate}, force_refresh: ${forceRefresh}`);
      
      // Call API
      const response = await axios.get('/api/v1/ad-metrics/dashboard/', {
        params: {
          start_date: startDate,
          end_date: endDate,
          force_refresh: forceRefresh
        },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        },
        timeout: 60000 // 60 seconds timeout for Facebook data fetching
      });
      
      console.log('Response received:', response.data);
      console.log('Refresh status:', response.data.refresh_status);
      
      // Debug ad metrics data
      console.log('Ad metrics data length:', response.data.ad_metrics ? response.data.ad_metrics.length : 0);
      console.log('First few ad metrics items:', response.data.ad_metrics?.slice(0, 3));
      console.log('Unique ads:', response.data.unique_ads);
      
      // Debug for campaign and adset data
      if (response.data.ad_metrics && response.data.ad_metrics.length > 0) {
        console.log('Campaign data available:', response.data.ad_metrics.some(m => m.campaign_name));
        console.log('Adset data available:', response.data.ad_metrics.some(m => m.adset_name));
        console.log('Sample ad metrics with campaign/adset:', response.data.ad_metrics.find(m => m.campaign_name || m.adset_name));
      }
      
      // Set data & check if we need to refetch
      if (response.data) {
        setMetrics(response.data);
        
        const refreshStatus = response.data.refresh_status;
        if (refreshStatus) {
          console.log(`Metrics fetched: ${refreshStatus.metrics_fetched}, Has complete data: ${refreshStatus.has_complete_data}`);
          
          // If force refresh was attempted but didn't fetch metrics, show warning
          if (refreshStatus.force_refresh_attempted && !refreshStatus.metrics_fetched) {
            toast({
              title: "Data refresh attempted",
              description: "We attempted to refresh your data, but no new data was fetched. This could be due to Facebook API limits or credentials issues.",
              variant: "default",
            });
          }
          
          // If we still don't have complete data after fetch, show info message
          if (!refreshStatus.has_complete_data) {
            toast({
              title: "Incomplete data",
              description: "Some data may be missing for the selected date range. Try a narrower range or check your Facebook connection.",
              variant: "default",
            });
          }
        }
      }
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError('Failed to load dashboard data');
      
      toast({
        title: "Error loading data",
        description: "There was a problem loading your dashboard data. Please try again later.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
      setIsFetchingFromFacebook(false);
      setForceRefresh(false); // Reset force refresh after attempt
    }
  };

  // Fetch metrics when date range changes
  useEffect(() => {
    fetchMetrics();
  }, [dateRange, user, fetchAttempts, forceRefresh]);

  // Helper to generate sample ad metrics data for testing
  const generateSampleAdData = () => {
    const adNames = ['Summer Sale Ad', 'Holiday Promotion', 'New Product Launch', 'Brand Awareness'];
    const adIds = ['ad_123456', 'ad_234567', 'ad_345678', 'ad_456789'];
    const campaignNames = ['Summer Campaign 2023', 'Holiday Campaign 2023', 'Product Launch Q4', 'Brand Awareness Q3'];
    const adsetNames = ['Mobile Users', 'Desktop Users', 'Retargeting Audience', 'Lookalike Audience'];
    const results = [];
    
    // Generate 30 days of data
    const today = new Date();
    for (let i = 0; i < 30; i++) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = format(date, 'yyyy-MM-dd');
      
      // Generate data for each ad
      for (let j = 0; j < adIds.length; j++) {
        // Add some randomness but keep a trend
        const dayFactor = Math.max(0.5, 1 - (i * 0.02)); // Slight downward trend for older dates
        const randomFactor = 0.7 + (Math.random() * 0.6); // Random variation between 0.7 and 1.3
        
        results.push({
          date: dateStr,
          ad_id: adIds[j],
          ad_name: adNames[j],
          campaign_name: campaignNames[j % campaignNames.length],
          adset_name: adsetNames[j % adsetNames.length],
          spend: 100 * dayFactor * randomFactor * (j + 1),
          revenue: 300 * dayFactor * randomFactor * (j + 1),
          clicks: Math.floor(1000 * dayFactor * randomFactor * (j + 0.5)),
          impressions: Math.floor(10000 * dayFactor * randomFactor * (j + 0.5)),
          purchases: Math.floor(50 * dayFactor * randomFactor * (j + 0.5)),
          ctr: 0.1 * randomFactor,
          cpc: 1.2 * randomFactor,
          cpm: 10 * randomFactor,
          roas: 3 * randomFactor
        });
      }
    }
    
    return results;
  };

  // Calculate percentage change
  const calculateChange = (current: number, previous: number): number => {
    if (previous === 0) return current > 0 ? 100 : 0;
    return ((current - previous) / previous) * 100;
  };

  // Render a KPI card
  const MetricCard = ({ 
    title, 
    value, 
    previousValue, 
    icon, 
    prefix = '', 
    suffix = '', 
    formatter = (n: number) => n.toFixed(2) 
  }: { 
    title: string; 
    value: number; 
    previousValue: number; 
    icon: React.ReactNode; 
    prefix?: string; 
    suffix?: string; 
    formatter?: (n: number) => string; 
  }) => {
    const change = calculateChange(value, previousValue);
    const isPositive = change >= 0;
    
    // For cost metrics (CPC, CPM), lower is better
    const isImproving = title.includes('Cost') ? !isPositive : isPositive;
    
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          <div className="h-4 w-4 text-muted-foreground">{icon}</div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {prefix}{formatter(value)}{suffix}
          </div>
          <div className="flex items-center pt-1 text-xs">
            {isImproving ? (
              <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
            ) : (
              <TrendingDown className="mr-1 h-3 w-3 text-red-500" />
            )}
            <span className={isImproving ? 'text-green-500' : 'text-red-500'}>
              {isPositive ? '+' : ''}{change.toFixed(1)}%
            </span>
            <span className="text-muted-foreground ml-1">vs previous period</span>
          </div>
        </CardContent>
      </Card>
    );
  };

  if (isLoading || isFetchingFromFacebook) {
    return (
      <div className="flex flex-col h-[calc(100vh-100px)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <span className="text-lg font-medium">
          {isFetchingFromFacebook 
            ? 'Fetching data from Facebook API...' 
            : 'Loading dashboard data...'}
        </span>
        {isFetchingFromFacebook && (
          <p className="text-sm text-muted-foreground mt-2 max-w-md text-center">
            This may take a minute as we're fetching daily metrics from Facebook for the selected date range.
          </p>
        )}
      </div>
    );
  }

  // Before the chart data preparation, add a function to group and find the highest value for each day
  // Get the maximum metrics value for each day
  const getMaxMetricsByDate = (metrics: AdMetricsData['daily_metrics'] | undefined) => {
    if (!metrics || metrics.length === 0) return [];
    
    // Group by date and find the max values
    const groupedByDate = metrics.reduce((acc, metric) => {
      const date = format(new Date(metric.date), 'MMM dd');
      if (!acc[date]) {
        acc[date] = {
          date,
          spend: metric.spend,
          revenue: metric.revenue,
          ctr: metric.ctr,
          roas: metric.roas
        };
      } else {
        // Take the highest value for each metric
        acc[date].spend = Math.max(acc[date].spend, metric.spend);
        acc[date].revenue = Math.max(acc[date].revenue, metric.revenue);
        acc[date].ctr = Math.max(acc[date].ctr, metric.ctr);
        acc[date].roas = Math.max(acc[date].roas, metric.roas);
      }
      
      return acc;
    }, {} as Record<string, { date: string; spend: number; revenue: number; ctr: number; roas: number }>);
    
    // Convert to array and sort by date
    return Object.values(groupedByDate).sort((a, b) => 
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );
  };

  // Get max metrics data for each day
  const maxDailyMetrics = getMaxMetricsByDate(metrics?.daily_metrics);

  // Prepare chart data for Plotly using the maximum values
  const spendRevenueData = [
    {
      x: maxDailyMetrics.map(day => day.date),
      y: maxDailyMetrics.map(day => day.spend),
      type: 'bar',
      name: 'Spend',
      marker: { color: 'rgba(99, 102, 241, 0.7)' }
    },
    {
      x: maxDailyMetrics.map(day => day.date),
      y: maxDailyMetrics.map(day => day.revenue),
      type: 'bar',
      name: 'Revenue',
      marker: { color: 'rgba(34, 197, 94, 0.7)' }
    }
  ];

  const roasData = [
    {
      x: maxDailyMetrics.map(day => day.date),
      y: maxDailyMetrics.map(day => day.roas),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'ROAS',
      line: { color: 'rgba(34, 197, 94, 0.7)' }
    }
  ];

  const ctrData = [
    {
      x: maxDailyMetrics.map(day => day.date),
      y: maxDailyMetrics.map(day => day.ctr * 100), // Convert to percentage
      type: 'scatter',
      mode: 'lines+markers',
      name: 'CTR',
      line: { color: 'rgba(99, 102, 241, 0.7)' }
    }
  ];

  // New Section: Ad Performance Overview
  const getTopAdsData = (dailyMetrics: AdMetricsData['daily_metrics'] | undefined) => {
    if (!dailyMetrics || dailyMetrics.length === 0) return [];
    
    // Create a map of unique ads with their aggregated metrics
    const adMetricsMap = new Map<string, { 
      name: string; 
      spend: number; 
      revenue: number; 
      impressions: number;
      clicks: number;
      roas: number; 
      ctr: number 
    }>();
    
    // Process each daily metric to aggregate by ad
    dailyMetrics.forEach(metric => {
      // Use date as a placeholder since we don't have ad_id/ad_name in the current model
      // In a real implementation, you would use metric.ad_id as the key
      const adId = metric.date; // Temporary: using date as ad identifier
      const adName = metric.date; // Temporary: using date as ad name
      
      if (!adMetricsMap.has(adId)) {
        adMetricsMap.set(adId, {
          name: adName,
          spend: metric.spend,
          revenue: metric.revenue,
          impressions: metric.impressions || 0,
          clicks: metric.clicks || 0,
          roas: metric.revenue > 0 && metric.spend > 0 ? metric.revenue / metric.spend : 0,
          ctr: metric.impressions > 0 && metric.clicks > 0 ? metric.clicks / metric.impressions : 0
        });
      } else {
        const existing = adMetricsMap.get(adId)!;
        existing.spend += metric.spend;
        existing.revenue += metric.revenue;
        existing.impressions += (metric.impressions || 0);
        existing.clicks += (metric.clicks || 0);
        
        // Recalculate derived metrics
        existing.roas = existing.spend > 0 ? existing.revenue / existing.spend : 0;
        existing.ctr = existing.impressions > 0 ? existing.clicks / existing.impressions : 0;
      }
    });
    
    // Convert map to array and sort by revenue (highest first)
    return Array.from(adMetricsMap.values())
      .sort((a, b) => b.revenue - a.revenue)
      .slice(0, 5); // Get top 5 ads
  };

  // Get Ad Metrics Chart Data
  const getAdMetricsChartData = (adMetrics: any[], metricName: string, formatter?: (value: number) => number) => {
    console.log(`getAdMetricsChartData called with ${adMetrics?.length || 0} items for metric: ${metricName}`);
    
    // If ad_metrics is empty, use the sample data
    if (!adMetrics || adMetrics.length === 0) {
      console.log('Using sample ad data for testing');
      adMetrics = generateSampleAdData();
    }
    
    // Log first ad metric to see its structure
    if (adMetrics.length > 0) {
      console.log('Sample ad metric structure:', adMetrics[0]);
    }
    
    // Log what we're working with
    console.log(`Working with ${adMetrics.length} metrics for the chart`);
    
    // Get unique ad IDs and their names
    const uniqueAds = new Map();
    adMetrics.forEach(metric => {
      if (metric.ad_id && metric.ad_name) {
        uniqueAds.set(metric.ad_id, metric.ad_name);
      }
    });
    
    console.log(`Found ${uniqueAds.size} unique ads`);
    
    // If no ad information, get unique ads from the separate unique_ads array
    if (uniqueAds.size === 0 && metrics?.unique_ads) {
      console.log('Using unique_ads array for ad info');
      metrics.unique_ads.forEach(ad => {
        if (ad.ad_id && ad.ad_name) {
          uniqueAds.set(ad.ad_id, ad.ad_name);
        }
      });
      console.log(`Now have ${uniqueAds.size} unique ads from unique_ads array`);
    }
    
    // If still no ad information, use sample data
    if (uniqueAds.size === 0) {
      console.log('No unique ads found, using sample data');
      return [];
    }
    
    // Generate colors for each ad - one color per ad
    const colors = [
      'rgba(99, 102, 241, 1)',  // Indigo
      'rgba(34, 197, 94, 1)',   // Green
      'rgba(249, 115, 22, 1)',  // Orange
      'rgba(236, 72, 153, 1)',  // Pink
      'rgba(168, 85, 247, 1)',  // Purple
      'rgba(59, 130, 246, 1)',  // Blue
      'rgba(234, 179, 8, 1)',   // Yellow
      'rgba(239, 68, 68, 1)',   // Red
      'rgba(20, 184, 166, 1)',  // Teal
      'rgba(75, 85, 99, 1)'     // Gray
    ];
    
    // Assign a color to each ad
    let colorIndex = 0;
    const adColors = {};
    uniqueAds.forEach((name, id) => {
      adColors[id] = colors[colorIndex % colors.length];
      colorIndex++;
    });
    
    // Extract campaign and adset info if available
    const campaignInfo = new Map();
    const adsetInfo = new Map();
    
    // Create a lookup for campaign and adset based on ad_id
    adMetrics.forEach(metric => {
      if (metric.ad_id) {
        // If campaign_name is available in the data, store it
        if (metric.campaign_name) {
          campaignInfo.set(metric.ad_id, metric.campaign_name);
        }
        
        // If adset_name is available in the data, store it
        if (metric.adset_name) {
          adsetInfo.set(metric.ad_id, metric.adset_name);
        }
      }
    });
    
    // If there's no campaign or adset info, enrich with fallback data by extracting from ad name
    uniqueAds.forEach((adName, adId) => {
      // Only set fallback if we don't have actual data
      if (!campaignInfo.has(adId)) {
        // Try to derive campaign name from ad name or use a generic name with the ad ID
        const derivedCampaign = adName.includes(' - ') 
          ? adName.split(' - ')[0]
          : `Campaign ${adId.substring(0, 6)}`;
        campaignInfo.set(adId, derivedCampaign);
      }
      
      if (!adsetInfo.has(adId)) {
        // Try to derive adset name from ad name or use a generic name with the ad ID
        const derivedAdset = adName.includes(' - ') && adName.split(' - ').length > 1
          ? adName.split(' - ')[1]
          : `Ad Set ${adId.substring(0, 6)}`;
        adsetInfo.set(adId, derivedAdset);
      }
    });
    
    // Group data by ad_id
    const adData = {};
    Array.from(uniqueAds.keys()).forEach(adId => {
      // Get campaign and adset names for this ad
      const campaignName = campaignInfo.get(adId) || 'Campaign Info Unavailable';
      const adsetName = adsetInfo.get(adId) || 'Ad Set Info Unavailable';
      
      adData[adId] = {
        x: [],
        y: [],
        type: 'scatter',
        mode: 'lines+markers',
        name: uniqueAds.get(adId) || adId.substring(0, 8),
        line: { color: adColors[adId], width: 2 },
        marker: { size: 6 },
        // Add customdata and hovertemplate for rich tooltips
        customdata: [],
        hovertemplate: '<b>%{customdata[0]}</b><br><br>Date: %{x}<br>' + 
          (metricName === 'ctr' ? 'CTR' : metricName.charAt(0).toUpperCase() + metricName.slice(1)) + ': %{y}<br><br>' +
          'Campaign: %{customdata[1]}<br>Ad Set: %{customdata[2]}<br><br>' +
          'Purchases: %{customdata[3]}<br>Spend: $%{customdata[4]}<br>Revenue: $%{customdata[5]}<br>' +
          'Clicks: %{customdata[6]}<br>Impressions: %{customdata[7]}<br>ROAS: %{customdata[8]}x<br>' +
          'CPC: $%{customdata[9]}<br>CPM: $%{customdata[10]}<extra></extra>'
      };
    });
    
    // Sort metrics by date
    const sortedMetrics = [...adMetrics].sort((a, b) => {
      return new Date(a.date).getTime() - new Date(b.date).getTime();
    });
    
    console.log(`Processing ${sortedMetrics.length} metrics sorted by date`);
    
    // Populate data for each ad
    sortedMetrics.forEach(metric => {
      if (metric.ad_id && adData[metric.ad_id]) {
        const date = format(new Date(metric.date), 'MMM dd');
        adData[metric.ad_id].x.push(date);
        
        // Apply formatter if provided
        const value = metric[metricName] ?? 0;
        adData[metric.ad_id].y.push(formatter ? formatter(value) : value);
        
        // Get campaign and adset names (from our lookup or from the metric itself)
        const campaignName = metric.campaign_name || campaignInfo.get(metric.ad_id) || 'Campaign Info Unavailable';
        const adsetName = metric.adset_name || adsetInfo.get(metric.ad_id) || 'Ad Set Info Unavailable';
        
        // Add custom data for tooltip with improved formatting
        adData[metric.ad_id].customdata.push([
          metric.ad_name || 'Unknown Ad',                  // Ad name
          campaignName,                                    // Campaign name (with fallback)
          adsetName,                                       // Ad set name (with fallback)
          metric.purchases || 0,                           // Purchases 
          (metric.spend || 0).toFixed(2),                  // Spend
          (metric.revenue || 0).toFixed(2),                // Revenue
          metric.clicks?.toLocaleString() || 0,            // Clicks with thousand separators
          metric.impressions?.toLocaleString() || 0,       // Impressions with thousand separators
          (metric.roas || 0).toFixed(2),                   // ROAS
          (metric.cpc || 0).toFixed(2),                    // CPC
          (metric.cpm || 0).toFixed(2)                     // CPM
        ]);
      }
    });
    
    // For debugging: Check what data we have for each ad
    Object.entries(adData).forEach(([adId, data]: [string, any]) => {
      console.log(`Ad ${adId} has ${data.x.length} data points`);
    });
    
    // Return only ads that have data points, limiting to 10 ads maximum to prevent overcrowding
    const dataArray = Object.values(adData)
      .filter((ad: any) => ad.x.length > 0)
      .slice(0, 10);
    
    console.log(`Returning ${dataArray.length} ads with data for charts`);
    return dataArray;
  };

  return (
    <div className="container mx-auto py-10 space-y-8 overflow-auto h-[calc(100vh-100px)]">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-4">
          <Tabs value={timeRange} onValueChange={handleTimeRangeChange} className="mr-4">
            <TabsList>
              <TabsTrigger value="today">Today</TabsTrigger>
              <TabsTrigger value="last7Days">Last 7 Days</TabsTrigger>
              <TabsTrigger value="last30Days">Last 30 Days</TabsTrigger>
              <TabsTrigger value="custom">Custom</TabsTrigger>
            </TabsList>
          </Tabs>
          <DateRangePicker
            value={dateRange}
            onChange={handleDateRangePickerChange}
          />
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => {
              setForceRefresh(true);
              console.log("Forcing refresh of data");
              toast({
                title: "Refreshing data",
                description: "Fetching latest data from Facebook...",
                variant: "default",
              });
            }}
            disabled={isLoading}
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh Data
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col h-[calc(100vh-100px)] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <span className="text-lg font-medium">
            Loading dashboard data...
          </span>
        </div>
      ) : (
        <div className="pb-10"> {/* Add padding at bottom for better scrolling */}
          {/* Main Dashboard Tabs */}
          <Tabs defaultValue="account" className="w-full mt-4">
            <TabsList className="mb-6">
              <TabsTrigger value="account">Account Performance</TabsTrigger>
              <TabsTrigger value="ads">Ad Performance</TabsTrigger>
            </TabsList>
            
            {/* Account Performance Tab */}
            <TabsContent value="account" className="space-y-6">
              {/* KPI Cards */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5 mb-6">
                <MetricCard 
                  title="ROAS" 
                  value={metrics?.current_period?.roas || 0} 
                  previousValue={metrics?.previous_period?.roas || 0} 
                  icon={<DollarSign />} 
                  formatter={(n) => n.toFixed(2)}
                  suffix="x"
                />
                <MetricCard 
                  title="CTR" 
                  value={metrics?.current_period?.ctr || 0} 
                  previousValue={metrics?.previous_period?.ctr || 0} 
                  icon={<MousePointerClick />} 
                  formatter={(n) => formatPercentage(n * 100)}
                  suffix="%"
                />
                <MetricCard 
                  title="CPC" 
                  value={metrics?.current_period?.cpc || 0} 
                  previousValue={metrics?.previous_period?.cpc || 0} 
                  icon={<MousePointerClick />} 
                  prefix="$"
                  formatter={(n) => formatCurrency(n)}
                />
                <MetricCard 
                  title="CPM" 
                  value={metrics?.current_period?.cpm || 0} 
                  previousValue={metrics?.previous_period?.cpm || 0} 
                  icon={<Eye />} 
                  prefix="$"
                  formatter={(n) => formatCurrency(n)}
                />
                <MetricCard 
                  title="Conversions" 
                  value={metrics?.current_period?.conversions || 0} 
                  previousValue={metrics?.previous_period?.conversions || 0} 
                  icon={<ShoppingCart />} 
                  formatter={(n) => n.toFixed(0)}
                />
              </div>

              {/* Account Performance Charts */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle>Daily Spend vs Revenue</CardTitle>
                    <CardDescription>
                      Compare your daily ad spend against generated revenue
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[300px]">
                    <PlotlyBarChart 
                      data={spendRevenueData}
                      layout={{
                        yaxis: { title: 'Amount ($)' }
                      }}
                    />
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle>ROAS Trend</CardTitle>
                    <CardDescription>
                      Return on ad spend over time
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[300px]">
                    <PlotlyLineChart 
                      data={roasData}
                      layout={{
                        yaxis: { title: 'ROAS' }
                      }}
                    />
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle>Click-Through Rate Trend</CardTitle>
                    <CardDescription>
                      CTR performance over time
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[300px]">
                    <PlotlyLineChart 
                      data={ctrData}
                      layout={{
                        yaxis: { title: 'CTR (%)' }
                      }}
                    />
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
            
            {/* Ad Performance Tab */}
            <TabsContent value="ads">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">Ad Performance</h2>
                <Button
                  variant="outline"
                  onClick={() => navigate('/app/ad-metrics')}
                >
                  View Detailed Ad Metrics
                </Button>
              </div>
              
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2 mb-6">
                <Card>
                  <CardHeader>
                    <CardTitle>ROAS by Ad</CardTitle>
                    <CardDescription>
                      Return on ad spend for each ad over time
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[400px]">
                    <PlotlyLineChart 
                      data={getAdMetricsChartData(metrics?.ad_metrics || [], 'roas')}
                      layout={{
                        yaxis: { title: 'ROAS' },
                        legend: { orientation: 'h', y: -0.3, xanchor: 'center', x: 0.5 },
                        margin: { l: 50, r: 20, t: 30, b: 100 }
                      }}
                    />
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle>CTR by Ad</CardTitle>
                    <CardDescription>
                      Click-through rate for each ad over time
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[400px]">
                    <PlotlyLineChart 
                      data={getAdMetricsChartData(metrics?.ad_metrics || [], 'ctr', value => value * 100)}
                      layout={{
                        yaxis: { title: 'CTR (%)' },
                        legend: { orientation: 'h', y: -0.3, xanchor: 'center', x: 0.5 },
                        margin: { l: 50, r: 20, t: 30, b: 100 }
                      }}
                    />
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle>Spend by Ad</CardTitle>
                    <CardDescription>
                      Daily spend for each ad
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[400px]">
                    <PlotlyLineChart 
                      data={getAdMetricsChartData(metrics?.ad_metrics || [], 'spend')}
                      layout={{
                        yaxis: { title: 'Spend ($)' },
                        legend: { orientation: 'h', y: -0.3, xanchor: 'center', x: 0.5 },
                        margin: { l: 50, r: 20, t: 30, b: 100 }
                      }}
                    />
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle>Revenue by Ad</CardTitle>
                    <CardDescription>
                      Daily revenue for each ad
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="h-[400px]">
                    <PlotlyLineChart 
                      data={getAdMetricsChartData(metrics?.ad_metrics || [], 'revenue')}
                      layout={{
                        yaxis: { title: 'Revenue ($)' },
                        legend: { orientation: 'h', y: -0.3, xanchor: 'center', x: 0.5 },
                        margin: { l: 50, r: 20, t: 30, b: 100 }
                      }}
                    />
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
};

export default Dashboard; 