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
  }>;
  refresh_status: {
    metrics_fetched: boolean;
    has_complete_data: boolean;
    force_refresh_attempted: boolean;
  };
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

          <div className="grid gap-4 md:grid-cols-2">
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
        </div>
      )}
    </div>
  );
};

export default Dashboard; 