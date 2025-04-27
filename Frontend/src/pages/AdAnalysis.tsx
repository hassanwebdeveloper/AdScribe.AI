import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, RefreshCw } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

interface AdAnalysisDetail {
  hook?: string;
  tone?: string;
  power_phrases?: string;
  visual?: string;
}

interface AdSetTargeting {
  age_max?: number;
  age_min?: number;
  age_range?: number[];
  genders?: number[];
  geo_locations?: Record<string, any>;
  brand_safety_content_filter_levels?: string[];
  targeting_automation?: Record<string, any>;
  [key: string]: any; // Allow any other fields
}

interface AdAnalysis {
  _id: string;
  user_id: string;
  ad_analysis?: AdAnalysisDetail;
  audio_description?: string;
  video_description?: string;
  campaign_id?: string;
  campaign_name?: string;
  adset_id?: string;
  adset_name?: string;
  adset_targeting?: AdSetTargeting;
  video_id?: string;
  ad_title?: string;
  ad_message?: string;
  ad_status?: string;
  video_url?: string;
  created_at: string;
}

// Function to convert URLs in text to clickable links
const linkifyText = (text: string | undefined): JSX.Element => {
  if (!text) return <></>;
  
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

// Function to render targeting fields dynamically
const renderTargetingFields = (targeting: AdSetTargeting | undefined) => {
  if (!targeting) return <p>No targeting information available</p>;
  
  // Basic fields to handle specially
  const specialFields = ['age_min', 'age_max', 'genders', 'geo_locations'];
  
  // Get all the other targeting keys that will be displayed
  const otherKeys = Object.keys(targeting)
    .filter(key => !specialFields.includes(key) && targeting[key] !== undefined && targeting[key] !== null);
  
  // Split into left and right columns evenly
  const leftColumnKeys = otherKeys.filter((_, i) => i % 2 === 0);
  const rightColumnKeys = otherKeys.filter((_, i) => i % 2 === 1);
  
  // Function to render a targeting field
  const renderField = (key: string) => {
    const value = targeting[key];
    
    // Format the key for display (convert snake_case to Title Case)
    const formattedKey = key
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
    
    // Format the value based on its type
    let formattedValue: React.ReactNode;
    
    if (Array.isArray(value)) {
      // Handle array values
      if (value.length === 0) {
        formattedValue = "None";
      } else if (typeof value[0] === 'string' || typeof value[0] === 'number') {
        // Format string/number arrays nicely
        formattedValue = value.join(', ');
      } else {
        // For complex arrays, join with commas
        formattedValue = value.map(item => 
          typeof item === 'object' ? JSON.stringify(item) : String(item)
        ).join(', ');
      }
    } else if (typeof value === 'object') {
      // Handle object values as nested elements
      const objEntries = Object.entries(value);
      
      // Ensure even distribution - calculate how many entries go in each column
      const totalEntries = objEntries.length;
      const entriesPerColumn = Math.ceil(totalEntries / 2);
      
      // Split evenly between columns
      const leftObjKeys = objEntries.slice(0, entriesPerColumn);
      const rightObjKeys = objEntries.slice(entriesPerColumn);
      
      formattedValue = (
        <div className="ml-2 mt-1 pl-2 border-l-2 border-gray-200">
          <div className="grid grid-cols-2 gap-x-2 gap-y-1">
            <div>
              {leftObjKeys.map(([subKey, subValue]) => {
                // Format the sub key for display
                const formattedSubKey = subKey
                  .split('_')
                  .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                  .join(' ');
                
                return (
                  <div key={`${key}-${subKey}`} className="text-xs mb-1">
                    <span className="font-bold text-gray-700">{formattedSubKey}: </span>
                    <span>
                      {typeof subValue === 'object'
                        ? JSON.stringify(subValue)
                        : String(subValue)
                      }
                    </span>
                  </div>
                );
              })}
            </div>
            <div>
              {rightObjKeys.map(([subKey, subValue]) => {
                // Format the sub key for display
                const formattedSubKey = subKey
                  .split('_')
                  .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                  .join(' ');
                
                return (
                  <div key={`${key}-${subKey}`} className="text-xs mb-1">
                    <span className="font-bold text-gray-700">{formattedSubKey}: </span>
                    <span>
                      {typeof subValue === 'object'
                        ? JSON.stringify(subValue)
                        : String(subValue)
                      }
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    } else {
      // Simple value, just convert to string
      formattedValue = String(value);
    }
    
    return (
      <div key={key} className="mb-1">
        <span className="font-bold text-gray-800">{formattedKey}: </span>
        {typeof value !== 'object' && <span>{formattedValue}</span>}
        {typeof value === 'object' && Array.isArray(value) && <span>{formattedValue}</span>}
        {typeof value === 'object' && !Array.isArray(value) && (
          <>
            <br />
            {formattedValue}
          </>
        )}
      </div>
    );
  };
  
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        {/* Special rendering for common fields */}
        <div className="mb-1">
          <span className="font-bold text-gray-800">Age Range: </span>
          <span>{targeting.age_min || 'N/A'} - {targeting.age_max || 'N/A'}</span>
        </div>
        
        <div className="mb-1">
          <span className="font-bold text-gray-800">Gender: </span>
          <span>
            {targeting.genders?.includes(1) ? 'Male' : ''}
            {targeting.genders?.includes(2) ? (targeting.genders?.includes(1) ? ', Female' : 'Female') : ''}
            {!targeting.genders || targeting.genders.length === 0 ? 'N/A' : ''}
          </span>
        </div>
        
        <div className="mb-1 col-span-2">
          <span className="font-bold text-gray-800">Locations: </span>
          <span>{targeting.geo_locations?.countries?.join(', ') || 'N/A'}</span>
        </div>
      </div>
      
      {/* Other targeting fields in two columns */}
      {otherKeys.length > 0 && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
          <div>
            {leftColumnKeys.map(key => renderField(key))}
          </div>
          <div>
            {rightColumnKeys.map(key => renderField(key))}
          </div>
        </div>
      )}
    </div>
  );
};

const AdAnalysis = () => {
  const [adAnalyses, setAdAnalyses] = useState<AdAnalysis[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token } = useAuth();
  const { toast } = useToast();

  const fetchAdAnalyses = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/v1/ad-analysis/', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      
      // Validate response data is an array
      if (Array.isArray(response.data)) {
        setAdAnalyses(response.data);
      } else {
        console.error('Expected array but got:', typeof response.data, response.data);
        setAdAnalyses([]);
        setError("Received invalid data format from server");
        toast({
          variant: "destructive",
          title: "Data Error",
          description: "Received unexpected data format from server"
        });
      }
    } catch (error: any) {
      console.error('Error fetching ad analyses:', error);
      
      let errorMessage = "Failed to fetch ad analyses";
      if (error.response?.status === 401) {
        errorMessage = "Authentication failed. Please log in again.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }
      
      setError(errorMessage);
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage
      });
    } finally {
      setLoading(false);
    }
  };

  const analyzeAds = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const response = await axios.post('/api/v1/ad-analysis/analyze/', {}, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        timeout: 900000 // 15 minute timeout
      });
      
      // Validate response data is an array
      if (Array.isArray(response.data)) {
        setAdAnalyses(prevAnalyses => [...response.data, ...prevAnalyses]);
        
        toast({
          title: "Success",
          description: "Ads analyzed successfully!"
        });
      } else {
        console.error('Expected array but got:', typeof response.data, response.data);
        setError("Received invalid data format from server");
        toast({
          variant: "destructive",
          title: "Data Error",
          description: "Received unexpected data format from server"
        });
      }
    } catch (error: any) {
      console.error('Error analyzing ads:', error);
      
      let errorMessage = "Failed to analyze ads. Please try again later.";
      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        errorMessage = "The request timed out after 15 minutes. Facebook's API may be slow or you have a very large number of ads to analyze. Please try again later with a smaller date range.";
      } else if (error.response?.status === 401) {
        errorMessage = "Authentication failed. Please log in again.";
      } else if (error.response?.status === 405) {
        errorMessage = "Method not allowed. API endpoint may have changed.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }
      
      setError(errorMessage);
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage
      });
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    fetchAdAnalyses();
  }, []);

  return (
    <div className="flex flex-col h-screen">
      <div className="bg-background py-4 px-8 border-b shadow-sm">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-3xl font-bold">Ad Analysis</h1>
          <div className="flex gap-3">
            <Button 
              variant="outline" 
              onClick={fetchAdAnalyses}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Refresh
            </Button>
            <Button 
              onClick={analyzeAds}
              disabled={analyzing}
            >
              {analyzing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              {analyzing ? "Analyzing..." : "Analyze Ads (May Take Up To 15 Minutes)"}
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto py-6 px-8">
        <div className="container mx-auto">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : analyzing ? (
            <div className="flex flex-col justify-center items-center h-64 text-center">
              <Loader2 className="h-8 w-8 animate-spin mb-4" />
              <p className="text-lg text-muted-foreground">Analyzing ads from Facebook...</p>
              <p className="text-sm text-muted-foreground mt-2">This may take up to 15 minutes. Please don't close this page.</p>
            </div>
          ) : error ? (
            <div className="flex flex-col justify-center items-center h-64 text-center">
              <p className="text-lg text-destructive mb-4">Error: {error}</p>
              <Button onClick={fetchAdAnalyses} variant="outline">Try Again</Button>
            </div>
          ) : adAnalyses.length === 0 ? (
            <div className="flex flex-col justify-center items-center h-64 text-center">
              <p className="text-lg text-muted-foreground mb-4">No ad analyses found.</p>
              <p className="text-muted-foreground mb-6">Click the "Analyze Ads" button to analyze your Facebook ads.</p>
              <Button onClick={analyzeAds} disabled={analyzing}>
                {analyzing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                {analyzing ? "Analyzing..." : "Analyze Ads (May Take Up To 15 Minutes)"}
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {adAnalyses.map((analysis) => (
                <Card key={analysis._id} className="overflow-hidden">
                  <CardHeader className="relative">
                    <div className="flex items-start justify-between">
                      <CardTitle className="pr-20">{analysis.ad_title || 'Untitled Ad'}</CardTitle>
                      <span className={`absolute top-4 right-6 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        analysis.ad_status === 'ACTIVE' 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {analysis.ad_status || 'Unknown'}
                      </span>
                    </div>
                    <CardDescription>
                      Campaign: {analysis.campaign_name || 'Unknown Campaign'}
                    </CardDescription>
                    {analysis.ad_message && (
                      <div className="mt-3 text-sm whitespace-pre-line">
                        {linkifyText(analysis.ad_message)}
                      </div>
                    )}
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-5">
                      <div>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Hook</p>
                            <p>{analysis.ad_analysis?.hook || 'N/A'}</p>
                          </div>
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Tone</p>
                            <p>{analysis.ad_analysis?.tone || 'N/A'}</p>
                          </div>
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Power Phrases</p>
                            <p>{analysis.ad_analysis?.power_phrases || 'N/A'}</p>
                          </div>
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Visual</p>
                            <p>{analysis.ad_analysis?.visual || 'N/A'}</p>
                          </div>
                        </div>
                      </div>
                      
                      <div>
                        <p className="font-bold text-gray-800 text-base mb-2">Targeting</p>
                        <div className="text-sm max-h-[200px] overflow-y-auto pr-2">
                          {renderTargetingFields(analysis.adset_targeting)}
                        </div>
                      </div>
                      
                      {analysis.video_url && (
                        <div className="h-[210px] flex items-center justify-center mt-1">
                          <video 
                            controls 
                            src={analysis.video_url} 
                            className="rounded-sm shadow-sm w-[290px] h-[180px] bg-gray-800 object-contain" 
                            preload="metadata"
                          />
                        </div>
                      )}
                      {!analysis.video_url && (
                        <div className="h-[210px]"></div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdAnalysis; 