import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import Plotly from 'plotly.js';
import createPlotlyComponent from 'react-plotly.js/factory';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

// Create a Plotly React component
const Plot = createPlotlyComponent(Plotly);

interface AdPerformanceSegmentsProps {
  startDate: string;
  endDate: string;
}

const AdPerformanceSegments: React.FC<AdPerformanceSegmentsProps> = ({ 
  startDate,
  endDate
}) => {
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [plotlyFigure, setPlotlyFigure] = useState<any>(null);
  const [segments, setSegments] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<string>('individual');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [adsPerPage] = useState<number>(8);
  const [plotType, setPlotType] = useState<'line' | 'distribution'>('line');
  const [segmentAttr, setSegmentAttr] = useState<'engagement_type' | 'fatigue_risk' | 'roas_classification'>('engagement_type');

  useEffect(() => {
    const fetchPlotlyData = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          setError('Authentication token missing');
          setIsLoading(false);
          return;
        }

        const response = await axios.get('/api/v1/visualization/ad-performance-segments', {
          params: {
            start_date: startDate,
            end_date: endDate
          },
          headers: {
            Authorization: `Bearer ${token}`
          }
        });

        if (response.data.figure) {
          // Parse the Plotly figure JSON
          const figureData = JSON.parse(response.data.figure);
          setPlotlyFigure(figureData);
          setSegments(response.data.segments || []);
        } else {
          setError(response.data.message || 'No data available for the selected period');
        }
      } catch (err: any) {
        console.error('Error fetching visualization:', err);
        setError(err.response?.data?.detail || 'Failed to load visualization');
      } finally {
        setIsLoading(false);
      }
    };

    if (startDate && endDate) {
      fetchPlotlyData();
    }
  }, [startDate, endDate]);

  // Memoized list of unique ads for select options
  const uniqueAds = useMemo(() => {
    const map: Record<string, string> = {};
    segments.forEach((s) => {
      if (s.ad_id) {
        map[s.ad_id] = s.ad_name || s.ad_id;
      }
    });
    return Object.entries(map).map(([id, name]) => ({ id, name }));
  }, [segments]);

  // Map segments by ad
  const adSegmentsMap = useMemo(() => {
    const map: Record<string, any[]> = {};
    segments.forEach((s) => {
      if (!map[s.ad_id]) map[s.ad_id] = [];
      map[s.ad_id].push(s);
    });
    return map;
  }, [segments]);

  const allAdIds = useMemo(() => Object.keys(adSegmentsMap), [adSegmentsMap]);

  const totalPages = Math.ceil(allAdIds.length / adsPerPage) || 1;

  const pagedAdIds = useMemo(() => {
    const startIndex = (currentPage - 1) * adsPerPage;
    return allAdIds.slice(startIndex, startIndex + adsPerPage);
  }, [allAdIds, currentPage, adsPerPage]);

  const goToPage = (page: number) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
  };

  const renderPlotForAd = (adId: string) => {
    const selectedAdSegments = adSegmentsMap[adId] || [];
    if (selectedAdSegments.length === 0) {
      return null;
    }

    // Helper mapper (shared for both plot types)
    const mapLabel = (val: string) => {
      if (!val) return 'Unknown';
      const v = val.toString().toLowerCase();
      if (segmentAttr === 'engagement_type') {
        if (v.includes('high engagement') && v.includes('low cost')) return 'eng ↑\ncost ↓';
        if (v.includes('high engagement') && v.includes('high cost')) return 'eng ↑\ncost ↑';
        if (v.includes('low engagement') && v.includes('high cost')) return 'eng ↓\ncost ↑';
        if (v.includes('low engagement') && v.includes('low cost')) return 'eng ↓\ncost ↓';
        return 'eng ?';
      }
      if (segmentAttr === 'fatigue_risk') {
        if (v.startsWith('low')) return 'fat ↓';
        if (v.startsWith('moderate')) return 'fat →';
        if (v.startsWith('high')) return 'fat ↑';
        return 'fat ?';
      }
      if (segmentAttr === 'roas_classification') {
        if (v.startsWith('profitable')) return 'ROAS ↑';
        if (v.startsWith('breakeven')) return 'ROAS →';
        if (v.startsWith('unprofitable')) return 'ROAS ↓';
        return 'ROAS ?';
      }
      return val;
    };

    const categoryOrderMap: Record<string, string[]> = {
      engagement_type: ['eng ↓\ncost ↓', 'eng ↓\ncost ↑', 'eng ↑\ncost ↓', 'eng ↑\ncost ↑'],
      fatigue_risk: ['fat ↓', 'fat →', 'fat ↑'],
      roas_classification: ['ROAS ↓', 'ROAS →', 'ROAS ↑'],
    };

    if (plotType === 'line') {
      // Single trace for ad showing segment value over time
      const sorted = [...selectedAdSegments].sort((a: any, b: any) => (a.date < b.date ? -1 : 1));

      // Format x-axis dates as 'Jun-06'
      const xDates = sorted.map((d: any) => format(parseISO(d.date), 'MMM-dd'));

      // Map y-axis labels depending on selected segment
      const labelForCategory = (cat: string) => mapLabel(cat);

      const yValues = sorted.map((d: any) => labelForCategory(d[segmentAttr]));

      const data: Partial<Plotly.PlotData>[] = [
        {
          x: xDates,
          y: yValues,
          mode: 'lines+markers',
          text: sorted.map((d: any) => {
            const segRaw = d[segmentAttr] ?? '';
            const segDisplay = segmentAttr === 'engagement_type'
              ? segRaw.toString().replace(', ', '<br>') // split long engagement text into two lines
              : segRaw;
            return (
              `Revenue: Rs.${(d.revenue ?? 0).toFixed(2)}` +
              `<br>CTR: ${(d.ctr ?? 0).toFixed(2)}%` +
              `<br>ROAS: ${(d.roas ?? 0).toFixed(2)}` +
              `<br>CPC: Rs.${(d.cpc ?? 0).toFixed(2)}` +
              (segDisplay ? `<br>${segDisplay}` : '')
            );
          }),
          hovertemplate: '%{x}<br>%{text}<extra></extra>',
          name: adId,
          line: { color: '#6366F1' },
          marker: { color: '#6366F1' },
        },
      ];

      const layout: Partial<Plotly.Layout> = {
        margin: { l: 40, r: 10, t: 10, b: 40 },
        xaxis: { title: '', type: 'category', tickangle: -45, tickfont: { size: 9 } },
        yaxis: {
          title: '',
          tickfont: { size: 9 },
          categoryorder: 'array',
          categoryarray: categoryOrderMap[segmentAttr] || [],
          tickangle: -45,
        },
        autosize: true,
      };

      return (
        <Plot
          data={data}
          layout={layout}
          config={{ displayModeBar: false, responsive: true }}
          useResizeHandler
          style={{ width: '100%', height: '100%' }}
        />
      );
    }

    // Distribution plot → histogram of Revenue grouped by selected segment attribute
    const labelForCategory = (cat: string) => mapLabel(cat);

    const counts: Record<string, number> = {};
    selectedAdSegments.forEach((s) => {
      const key = labelForCategory(s[segmentAttr] || 'Unknown');
      counts[key] = (counts[key] ?? 0) + 1;
    });

    const data: Partial<Plotly.PlotData>[] = [
      {
        x: Object.keys(counts),
        y: Object.values(counts),
        type: 'bar',
        marker: { color: '#3182CE' },
      },
    ];

    const layout: Partial<Plotly.Layout> = {
      margin: { l: 40, r: 10, t: 10, b: 40 },
      xaxis: { title: '', type: 'category', tickfont: { size: 9 } },
      yaxis: { title: '', tickfont: { size: 9 }, tickangle: -45 },
      autosize: true,
    };

    return (
      <Plot
        data={data}
        layout={layout}
        config={{ displayModeBar: false, responsive: true }}
        useResizeHandler
        style={{ width: '100%', height: '100%' }}
      />
    );
  };

  if (isLoading) {
    return (
      <Card className="col-span-4">
        {/* <CardHeader className="pb-2">
          <CardTitle>Ad Performance Segments</CardTitle>
        </CardHeader> */}
        <CardContent className="flex items-center justify-center h-[600px]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-2">Loading visualization...</span>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="col-span-4">
        {/* <CardHeader className="pb-2">
          <CardTitle>Ad Performance Segments</CardTitle>
        </CardHeader> */}
        <CardContent className="flex items-center justify-center h-[600px]">
          <div className="text-center text-muted-foreground">
            <p>{error}</p>
            <p className="mt-2">Try selecting a different date range or refreshing the data.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="col-span-4">
      <CardContent className="p-2 md:p-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="individual">Individual Ads</TabsTrigger>
            <TabsTrigger value="combined">Combined</TabsTrigger>
          </TabsList>

          {/* Individual Tab */}
          <TabsContent value="individual" className="space-y-4">
            {/* Controls */}
            <div className="flex flex-col md:flex-row gap-4">
              <Select value={plotType} onValueChange={(val: any) => setPlotType(val)}>
                <SelectTrigger className="w-full md:w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="line">Line</SelectItem>
                  <SelectItem value="distribution">Distribution</SelectItem>
                </SelectContent>
              </Select>

              <Select value={segmentAttr} onValueChange={(val: any) => setSegmentAttr(val)}>
                <SelectTrigger className="w-full md:w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="engagement_type">Engagement Type</SelectItem>
                  <SelectItem value="fatigue_risk">Fatigue Risk</SelectItem>
                  <SelectItem value="roas_classification">ROAS Classification</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Plots grid */}
            {segments.length === 0 ? (
              <div className="flex items-center justify-center h-[400px] text-muted-foreground">No data available</div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {pagedAdIds.map((adId) => {
                    const segs = adSegmentsMap[adId] || [];
                    const { ad_name = adId, campaign_name = '' } = segs[0] || {};
                    return (
                      <div key={adId} className="border rounded-md p-3 h-[260px] flex flex-col">
                        <div className="mb-1">
                          <p className="text-sm font-semibold line-clamp-2">{ad_name}</p>
                          {campaign_name && <p className="text-xs text-muted-foreground line-clamp-1">{campaign_name}</p>}
                        </div>
                        <div className="flex-1">
                          {renderPlotForAd(adId)}
                        </div>
                      </div>
                    );
                  })}
                </div>
                {totalPages > 1 && (
                  <Pagination className="mt-4">
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious onClick={() => goToPage(currentPage - 1)} aria-disabled={currentPage === 1} />
                      </PaginationItem>
                      {[...Array(totalPages)].map((_, idx) => {
                        const pageNum = idx + 1;
                        return (
                          <PaginationItem key={pageNum}>
                            <PaginationLink isActive={pageNum === currentPage} onClick={() => goToPage(pageNum)}>
                              {pageNum}
                            </PaginationLink>
                          </PaginationItem>
                        );
                      })}
                      <PaginationItem>
                        <PaginationNext onClick={() => goToPage(currentPage + 1)} aria-disabled={currentPage === totalPages} />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                )}
              </>
            )}
          </TabsContent>

          {/* Combined Tab */}
          <TabsContent value="combined">
            {plotlyFigure ? (
              <div className="h-[1000px] w-full">
                <Plot
                  data={plotlyFigure.data}
                  layout={plotlyFigure.layout}
                  config={{ responsive: true, displayModeBar: false }}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-[600px] text-muted-foreground">
                No data available for the selected period
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

export default AdPerformanceSegments; 