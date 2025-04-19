import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Ad } from '@/types';

interface AdCardProps {
  ad: Ad | any;
}

const AdCard: React.FC<AdCardProps> = ({ ad }) => {
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

  return (
    <Card className="w-full mt-3 mb-3 border-green-200 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <CardTitle className="text-green-800 text-base">{parsedAd.title}</CardTitle>
          <Badge variant="outline" className="bg-green-50 text-green-700 ml-2">
            Sponsored
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pb-2">
        <CardDescription className="whitespace-pre-line text-sm">{parsedAd.description}</CardDescription>
        
        {parsedAd.video_url && (
          <div className="mt-3">
            <video 
              controls 
              src={parsedAd.video_url} 
              className="w-full rounded-md shadow-sm"
              preload="metadata"
            />
          </div>
        )}
      </CardContent>
      <CardFooter className="text-xs text-gray-500 flex justify-between pt-1">
        <span>{parsedAd.purchases} purchases</span>
        {parsedAd.is_active && <span className="text-green-600">Available Now</span>}
      </CardFooter>
    </Card>
  );
};

export default AdCard; 