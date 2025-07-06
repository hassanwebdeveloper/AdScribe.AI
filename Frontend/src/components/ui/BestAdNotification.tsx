import React from 'react';
import { 
  AlertCircle, 
  TrendingUp, 
  Info,
  LineChart
} from 'lucide-react';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { 
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';

interface BestAdNotificationProps {
  adId: string;
  adName: string;
  metrics: {
    roas: number;
    ctr: number;
    cpc: number;
    cpm: number;
    conversions: number;
    revenue: number;
  };
  onClose: () => void;
}

const BestAdNotification: React.FC<BestAdNotificationProps> = ({
  adId,
  adName,
  metrics,
  onClose
}) => {
  const navigate = useNavigate();

  const handleViewAd = () => {
    // Navigate to ad details page
    navigate(`/ads/${adId}`);
    onClose();
  };

  return (
    <Card className="w-[350px] shadow-lg border-l-4 border-l-blue-500 animate-in slide-in-from-right">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <div className="flex items-center">
            <TrendingUp className="h-5 w-5 text-blue-500 mr-2" />
            <CardTitle className="text-sm font-medium">Predicted Best Performer</CardTitle>
          </div>
          <button 
            onClick={onClose}
            className="rounded-full h-6 w-6 inline-flex items-center justify-center text-gray-500 hover:text-gray-700"
          >
            <span className="sr-only">Close</span>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex items-center mt-1">
          <CardDescription className="text-xs mr-2">
            Based on time series forecasting for upcoming days
          </CardDescription>
          <Badge variant="outline" className="h-5 text-[10px] px-1 flex items-center bg-blue-50">
            <LineChart className="h-3 w-3 mr-1" />
            ARIMA
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-sm font-semibold mb-2 truncate" title={adName}>
          {adName}
        </div>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">ROAS</span>
            <span className="font-medium">{metrics.roas.toFixed(2)}x</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">CTR</span>
            <span className="font-medium">{formatPercentage(metrics.ctr)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">CPC</span>
            <span className="font-medium">Rs.{formatCurrency(metrics.cpc)}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-gray-500">Conversions</span>
            <span className="font-medium">{Math.round(metrics.conversions)}</span>
          </div>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          className="w-full"
          onClick={handleViewAd}
        >
          <Info className="h-4 w-4 mr-1" />
          View Ad Details
        </Button>
      </CardContent>
      <CardFooter className="pt-0 px-6 pb-4">
        <p className="text-[10px] text-muted-foreground">
          Predictions use ARIMA and exponential smoothing time series forecasting for increased accuracy
        </p>
      </CardFooter>
    </Card>
  );
};

export default BestAdNotification; 