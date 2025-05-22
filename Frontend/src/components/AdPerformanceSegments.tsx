import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import axios from 'axios';
import { format } from 'date-fns';
import Plotly from 'plotly.js';
import createPlotlyComponent from 'react-plotly.js/factory';

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
      {/* <CardHeader className="pb-2">
        <CardTitle>Ad Performance Segments</CardTitle>
      </CardHeader> */}
      <CardContent className="p-2 md:p-6">
        {/* Mobile warning message */}
        <div className="block md:hidden p-4 mb-4 bg-amber-50 border border-amber-200 rounded-md text-amber-800">
          <p className="font-medium">This visualization is optimized for larger screens</p>
          <p className="text-sm mt-1">For the best experience, please view on a tablet or desktop device.</p>
        </div>
        
        {plotlyFigure ? (
          <div className="h-[1000px] w-full">
            <Plot
              data={plotlyFigure.data}
              layout={plotlyFigure.layout}
              config={{
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
              }}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-[600px] text-muted-foreground">
            No data available for the selected period
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AdPerformanceSegments; 