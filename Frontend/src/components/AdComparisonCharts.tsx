import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import axios from 'axios';
import { format } from 'date-fns';
import Plotly from 'plotly.js';
import createPlotlyComponent from 'react-plotly.js/factory';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';

// Create a Plotly React component
const Plot = createPlotlyComponent(Plotly);

interface AdComparisonChartsProps {
  startDate: string;
  endDate: string;
}

const AdComparisonCharts: React.FC<AdComparisonChartsProps> = ({ 
  startDate,
  endDate
}) => {
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [adMetrics, setAdMetrics] = useState<any[]>([]);
  const [uniqueAds, setUniqueAds] = useState<any[]>([]);
  
  // Add state for metric selection
  const [primaryMetric, setPrimaryMetric] = useState<string>('spend');
  const [secondaryMetric, setSecondaryMetric] = useState<string>('revenue');
  
  // Add pagination state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [adsPerPage] = useState<number>(6); // Show 6 ads per page for comparison charts

  useEffect(() => {
    const fetchAdMetricsData = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          setError('Authentication token missing');
          setIsLoading(false);
          return;
        }

        const response = await axios.get('/api/v1/ad-metrics/by-ad/', {
          params: {
            start_date: startDate,
            end_date: endDate
          },
          headers: {
            Authorization: `Bearer ${token}`
          }
        });

        if (response.data && response.data.ad_metrics && response.data.ad_metrics.length > 0) {
          setAdMetrics(response.data.ad_metrics);
          setUniqueAds(response.data.unique_ads || []);
        } else {
          setError('No ad metrics data available for the selected period');
        }
      } catch (err: any) {
        console.error('Error fetching ad metrics data:', err);
        setError(err.response?.data?.detail || 'Failed to load ad metrics data');
      } finally {
        setIsLoading(false);
      }
    };

    if (startDate && endDate) {
      fetchAdMetricsData();
    }
  }, [startDate, endDate]);

  const getMetricColor = (metric: string) => {
    const colorMap: Record<string, string> = {
      'spend': 'rgba(147, 51, 234, 0.7)',      // Purple for spend
      'revenue': 'rgba(34, 197, 94, 0.7)',      // Green for revenue
      'clicks': 'rgba(59, 130, 246, 0.7)',      // Blue for clicks
      'impressions': 'rgba(249, 115, 22, 0.7)', // Orange for impressions
      'ctr': 'rgba(236, 72, 153, 0.7)',         // Pink for CTR
      'cpc': 'rgba(168, 85, 247, 0.7)',         // Purple for CPC
      'cpm': 'rgba(20, 184, 166, 0.7)',         // Teal for CPM
      'roas': 'rgba(234, 179, 8, 0.7)',         // Yellow for ROAS
      'purchases': 'rgba(239, 68, 68, 0.7)'     // Red for purchases
    };
    
    return colorMap[metric] || 'rgba(99, 102, 241, 0.7)';
  };
  
  const getMetricTitle = (metric: string) => {
    const titleMap: Record<string, string> = {
      'spend': 'Spend ($)',
      'revenue': 'Revenue ($)',
      'clicks': 'Clicks',
      'impressions': 'Impressions',
      'purchases': 'Purchases',
      'ctr': 'CTR (%)',
      'cpc': 'CPC ($)',
      'cpm': 'CPM ($)',
      'roas': 'ROAS'
    };
    
    return titleMap[metric] || metric.charAt(0).toUpperCase() + metric.slice(1);
  };

  const generateComparisonCharts = () => {
    if (!adMetrics.length || !uniqueAds.length) {
      return (
        <div className="flex items-center justify-center h-[400px] text-muted-foreground">
          No data available for the selected period
        </div>
      );
    }

    // Group metrics by ad_id
    const adMetricsMap = new Map();
    adMetrics.forEach(metric => {
      if (!adMetricsMap.has(metric.ad_id)) {
        adMetricsMap.set(metric.ad_id, []);
      }
      adMetricsMap.get(metric.ad_id).push(metric);
    });
    
    // Convert to array for pagination
    const allAds = Array.from(adMetricsMap.entries());
    
    // Calculate pagination
    const totalAds = allAds.length;
    const totalPages = Math.ceil(totalAds / adsPerPage);
    const startIndex = (currentPage - 1) * adsPerPage;
    const endIndex = startIndex + adsPerPage;
    
    // Get current page ads
    const currentAds = allAds.slice(startIndex, endIndex);

    // Create comparison charts for each ad
    return (
      <>
        <div className="flex justify-between items-center mb-4">
          <p className="text-sm text-muted-foreground">
            Showing {startIndex + 1}-{Math.min(endIndex, totalAds)} of {totalAds} ads
          </p>
          {totalPages > 1 && (
            <div className="text-sm text-muted-foreground">
              Page {currentPage} of {totalPages}
            </div>
          )}
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {currentAds.map(([adId, metrics]) => {
            const adInfo = uniqueAds.find(ad => ad.ad_id === adId) || { ad_name: `Ad ${adId}` };
            const adName = adInfo.ad_title || adInfo.ad_name || `Ad ${adId}`;
            
            // Sort metrics by date
            const sortedMetrics = [...metrics].sort((a, b) => 
              new Date(a.date).getTime() - new Date(b.date).getTime()
            );
            
            // Format dates for display
            const dates = sortedMetrics.map(m => format(new Date(m.date), 'MMM dd'));
            
            // Extract primary and secondary metric data
            const primaryData = sortedMetrics.map(m => m[primaryMetric] || 0);
            const secondaryData = sortedMetrics.map(m => m[secondaryMetric] || 0);
            
            // Create chart data
            const chartData = [
              {
                x: dates,
                y: primaryData,
                type: 'bar',
                name: getMetricTitle(primaryMetric),
                marker: { color: getMetricColor(primaryMetric) }
              },
              {
                x: dates,
                y: secondaryData,
                type: 'bar',
                name: getMetricTitle(secondaryMetric),
                marker: { color: getMetricColor(secondaryMetric) }
              }
            ];
            
            // Chart layout
            const layout = {
              title: {
                text: adName,
                font: { size: 16 }
              },
              barmode: 'group',
              xaxis: {
                title: 'Date',
                tickangle: -45
              },
              yaxis: {
                title: 'Value'
              },
              legend: {
                orientation: 'h',
                y: -0.2
              },
              margin: { l: 50, r: 20, t: 40, b: 80 },
              height: 350
            };
            
            return (
              <Card key={adId} className="mb-6">
                <CardContent className="p-4">
                  <Plot
                    data={chartData}
                    layout={layout}
                    config={{
                      responsive: true,
                      displayModeBar: false
                    }}
                    style={{ width: '100%', height: '100%' }}
                  />
                </CardContent>
              </Card>
            );
          })}
        </div>
        
        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex justify-center mt-8">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious 
                    href="#" 
                    onClick={(e) => {
                      e.preventDefault();
                      if (currentPage > 1) {
                        setCurrentPage(currentPage - 1);
                      }
                    }}
                    className={currentPage <= 1 ? "pointer-events-none opacity-50" : ""}
                  />
                </PaginationItem>
                
                {/* Generate page numbers */}
                {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                  // Logic to show pages around current page
                  let pageNum;
                  if (totalPages <= 5) {
                    // If 5 or fewer pages, show all
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    // If near start, show first 5
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    // If near end, show last 5
                    pageNum = totalPages - 4 + i;
                  } else {
                    // Otherwise show 2 before and 2 after current
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <PaginationItem key={pageNum}>
                      <PaginationLink 
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          setCurrentPage(pageNum);
                        }}
                        isActive={currentPage === pageNum}
                      >
                        {pageNum}
                      </PaginationLink>
                    </PaginationItem>
                  );
                })}
                
                <PaginationItem>
                  <PaginationNext 
                    href="#" 
                    onClick={(e) => {
                      e.preventDefault();
                      if (currentPage < totalPages) {
                        setCurrentPage(currentPage + 1);
                      }
                    }}
                    className={currentPage >= totalPages ? "pointer-events-none opacity-50" : ""}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2">Loading comparison charts...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[400px] text-muted-foreground">
        <div className="text-center">
          <p>{error}</p>
          <p className="mt-2">Try selecting a different date range or refreshing the data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Metric selection controls */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="flex items-center gap-2">
          <Label htmlFor="primary-metric" className="text-sm">Primary Metric</Label>
          <Select
            value={primaryMetric}
            onValueChange={setPrimaryMetric}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select primary metric" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="spend">Spend</SelectItem>
              <SelectItem value="revenue">Revenue</SelectItem>
              <SelectItem value="clicks">Clicks</SelectItem>
              <SelectItem value="impressions">Impressions</SelectItem>
              <SelectItem value="purchases">Purchases</SelectItem>
              <SelectItem value="ctr">CTR</SelectItem>
              <SelectItem value="cpc">CPC</SelectItem>
              <SelectItem value="cpm">CPM</SelectItem>
              <SelectItem value="roas">ROAS</SelectItem>
            </SelectContent>
          </Select>
        </div>
        
        <div className="flex items-center gap-2">
          <Label htmlFor="secondary-metric" className="text-sm">Secondary Metric</Label>
          <Select
            value={secondaryMetric}
            onValueChange={setSecondaryMetric}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select secondary metric" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="spend">Spend</SelectItem>
              <SelectItem value="revenue">Revenue</SelectItem>
              <SelectItem value="clicks">Clicks</SelectItem>
              <SelectItem value="impressions">Impressions</SelectItem>
              <SelectItem value="purchases">Purchases</SelectItem>
              <SelectItem value="ctr">CTR</SelectItem>
              <SelectItem value="cpc">CPC</SelectItem>
              <SelectItem value="cpm">CPM</SelectItem>
              <SelectItem value="roas">ROAS</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      
      {/* Mobile warning message */}
      <div className="block md:hidden p-4 mb-4 bg-amber-50 border border-amber-200 rounded-md text-amber-800">
        <p className="font-medium">These charts are optimized for larger screens</p>
        <p className="text-sm mt-1">For the best experience, please view on a tablet or desktop device.</p>
      </div>
      
      {/* Render comparison charts */}
      {generateComparisonCharts()}
    </div>
  );
};

export default AdComparisonCharts; 