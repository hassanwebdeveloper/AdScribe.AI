import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Ad } from '@/types';
import { format, differenceInDays } from 'date-fns';
import { CalendarRange } from 'lucide-react';

interface AdCardProps {
  ad: Ad | any;
  start_date?: Date;
  end_date?: Date;
}

// Function to convert URLs in text to hyperlinks
const linkifyText = (text: string): JSX.Element => {
  // URL regex pattern
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  
  // Split the text by URLs
  const parts = text.split(urlRegex);
  
  // Match all URLs
  const matches = text.match(urlRegex) || [];
  
  // Combine parts and matched URLs
  const elements: JSX.Element[] = [];
  
  parts.forEach((part, i) => {
    elements.push(<span key={`part-${i}`}>{part}</span>);
    if (matches[i]) {
      elements.push(
        <a 
          key={`link-${i}`} 
          href={matches[i]} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="text-blue-600 hover:underline"
        >
          {matches[i]}
        </a>
      );
    }
  });
  
  return <>{elements}</>;
};

const AdCard: React.FC<AdCardProps> = ({ ad, start_date, end_date }) => {
  const [parsedAd, setParsedAd] = useState<Ad>({
    title: '',
    description: '',
    video_url: '',
    is_active: true,
    purchases: 0
  });

  useEffect(() => {
    // Parse ad data if it's a string
    try {
      let adData: any = ad;
      
      // If ad is a JSON string, parse it
      if (typeof ad === 'string') {
        console.log('Ad is a string, attempting to parse:', ad.substring(0, 100));
        
        // Handle common malformed JSON structure we're seeing
        // Example: {"title": Cash refund if not satisfied, "description":100% Pure White...}
        if (ad.startsWith('{') && ad.includes('"title":') && !ad.includes(':"')) {
          console.log('Found malformed JSON-like string, attempting manual extraction');
          // Extract fields using regex
          const titleMatch = ad.match(/"title":\s*([^,"]+)/);
          const descMatch = ad.match(/"description":\s*([^,"]+)/);
          const videoMatch = ad.match(/"video_url":\s*([^,"]+)/);
          const isActiveMatch = ad.match(/"is_active":\s*(true|false)/);
          const purchasesMatch = ad.match(/"purchases":\s*(\d+)/);
          
          adData = {
            title: titleMatch ? titleMatch[1].trim() : 'Sponsored Content',
            description: descMatch ? descMatch[1].trim() : ad,
            video_url: videoMatch ? videoMatch[1].trim() : '',
            is_active: isActiveMatch ? isActiveMatch[1] === 'true' : true,
            purchases: purchasesMatch ? parseInt(purchasesMatch[1].trim()) : 0
          };
          
          console.log('Manually extracted ad data:', adData);
        } else {
          // Standard JSON parsing attempt
          try {
            adData = JSON.parse(ad);
            console.log('Successfully parsed ad JSON:', adData);
          } catch (e) {
            console.error('Failed to parse ad string as JSON:', e);
            
            // Keep the string as the description
            adData = {
              title: 'Sponsored Content',
              description: ad,
              video_url: '',
              is_active: true,
              purchases: 0
            };
          }
        }
      }

      // Ensure we have valid values even if ad object is incomplete
      const safeAd = {
        title: adData.title || 'Sponsored Content',
        description: adData.description || 'No description available',
        video_url: adData.video_url || '',
        is_active: adData.is_active !== undefined ? adData.is_active : true,
        purchases: adData.purchases !== undefined ? adData.purchases : 0
      };

      console.log('Processed ad data:', safeAd);
      setParsedAd(safeAd);
    } catch (error) {
      console.error('Error processing ad data:', error);
      // Fallback to defaults
      setParsedAd({
        title: 'Sponsored Content',
        description: typeof ad === 'string' ? ad : 'No description available',
        video_url: '',
        is_active: true,
        purchases: 0
      });
    }
  }, [ad]);

  // Calculate duration in days if both dates are provided
  const duration = (start_date && end_date) ? 
    differenceInDays(new Date(end_date), new Date(start_date)) + 1 : // +1 to include both start and end dates
    null;

  return (
    <Card className="mt-3 mb-3 border-green-200 shadow-sm max-w-md mx-auto">
      <CardHeader className="pb-2 py-3">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-green-800 text-base">{parsedAd.title}</CardTitle>
            <div className="mt-1 space-y-0.5">
              {parsedAd.purchases > 0 && (
                <div className="text-sm font-medium text-gray-600">
                  {parsedAd.purchases} purchases
                </div>
              )}
              
              {start_date && end_date && (
                <div className="text-xs text-gray-500 flex items-center gap-1">
                  <CalendarRange className="h-3 w-3 text-gray-400" /> 
                  <span>{format(new Date(start_date), 'MMM d')} - {format(new Date(end_date), 'MMM d')}</span>
                  <span className="font-medium text-green-700">
                    ({duration} day{duration !== 1 ? 's' : ''})
                  </span>
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-1 items-end">
            <Badge variant="outline" className="bg-green-50 text-green-700">
              Highest Sold
            </Badge>
            {parsedAd.is_active ? (
              <Badge className="bg-green-500 text-white font-medium rounded-full px-3 py-0.5 text-xs">
                Active
              </Badge>
            ) : (
              <Badge className="bg-gray-500 text-white font-medium rounded-full px-3 py-0.5 text-xs">
                Not Active
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pb-2 pt-0 px-3">
        <div className="whitespace-pre-line text-sm mb-3">
          {linkifyText(parsedAd.description)}
        </div>
        
        {parsedAd.video_url && (
          <div className="mt-3 flex justify-center">
            <video 
              controls 
              src={parsedAd.video_url} 
              className="rounded-md shadow-sm w-[372px] aspect-[4/3]" 
              preload="metadata"
            />
          </div>
        )}
      </CardContent>
      <CardFooter className="text-xs text-gray-500 pt-1 py-2 px-3 flex items-center">
        {/* Date range moved to header section */}
      </CardFooter>
    </Card>
  );
};

export default AdCard; 