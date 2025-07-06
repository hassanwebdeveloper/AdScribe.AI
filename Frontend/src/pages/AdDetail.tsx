import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ChevronLeft, Loader2, Edit3, Check, X } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlotlyLineChart } from '@/components/ui/plotly-chart';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import axios from 'axios';

// Import the interfaces from AdAnalysis page
interface AdAnalysisDetail {
  hook?: string;
  tone?: string;
  power_phrases?: string;
  visual?: string;
  product?: string;
  product_type?: string;
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
  ad_id?: string;
}

// Interface for ad metrics
interface AdMetric {
  date: string;
  ad_id: string;
  ad_name: string;
  ad_title?: string;
  campaign_id?: string;
  campaign_name?: string;
  spend: number;
  clicks: number;
  impressions: number;
  purchases: number;
  revenue: number;
  ctr: number;
  cpc: number;
  cpm: number;
  roas: number;
}

// Interface for forecast data
interface ForecastData {
  dates: string[];
  values: number[];
  metric: string;
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
      
      formattedValue = (
        <div className="ml-2 mt-1 pl-2 border-l-2 border-gray-200">
          {objEntries.map(([subKey, subValue]) => {
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
      );
    } else {
      // Simple value, just convert to string
      formattedValue = String(value);
    }
    
    return (
      <div key={key} className="mb-2">
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
    <div className="space-y-4">
      {/* Special rendering for common fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
      </div>
      
      <div className="mb-1">
        <span className="font-bold text-gray-800">Locations: </span>
        <span>{targeting.geo_locations?.countries?.join(', ') || 'N/A'}</span>
      </div>
      
      {/* Other targeting fields */}
      {otherKeys.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {otherKeys.map(key => renderField(key))}
        </div>
      )}
    </div>
  );
};

const AdDetail = () => {
  const { id } = useParams<{ id: string }>();
  const [adAnalysis, setAdAnalysis] = useState<AdAnalysis | null>(null);
  const [adMetrics, setAdMetrics] = useState<AdMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [selectedMetricTab, setSelectedMetricTab] = useState('spend');
  const [showForecast, setShowForecast] = useState(false);
  const [forecastData, setForecastData] = useState<Record<string, ForecastData>>({});
  const [forecastLoading, setForecastLoading] = useState(false);
  const [editingFields, setEditingFields] = useState<{product?: boolean, product_type?: boolean}>({});
  const [editValues, setEditValues] = useState<{product?: string, product_type?: string}>({});
  const { token } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();

  // Get the current date and 30 days ago for metrics date range
  const today = new Date();
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(today.getDate() - 30);
  
  // Format dates as YYYY-MM-DD
  const formatDate = (date: Date) => {
    return date.toISOString().split('T')[0];
  };
  
  const endDate = formatDate(today);
  const startDate = formatDate(thirtyDaysAgo);

  // Fetch ad detail
  useEffect(() => {
    const fetchAdDetail = async () => {
      if (!id) return;
      
      setLoading(true);
      setError(null);
      
      try {
        console.log('Fetching ad detail for ID:', id);
        
        // Create a new endpoint that uses 'get' in the path to avoid conflict with the ID parameter
        const response = await axios.get(`/api/v1/ad-analysis/get/${id}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        
        console.log('Ad detail API response:', response.data);
        
        if (response.data) {
          // Transform the data if needed (MongoDB _id to id if necessary)
          const data = { ...response.data }; // Create a copy to avoid modifying the original
          
          // Ensure _id is properly handled
          if (data._id) {
            data.id = data._id;
            console.log('Using MongoDB _id:', data._id);
          } else {
            console.warn('No _id found in response data');
          }
          
          // Log fields important for rendering
          console.log('Ad title:', data.ad_title);
          console.log('Ad status:', data.ad_status);
          console.log('Campaign name:', data.campaign_name);
          console.log('Ad analysis fields present:', data.ad_analysis ? Object.keys(data.ad_analysis) : 'No ad_analysis object');
          
          setAdAnalysis(data);
        } else {
          console.error('Received empty response from server');
          setError("Received empty response from server");
          toast({
            variant: "destructive",
            title: "Error",
            description: "Received empty response from server"
          });
        }
      } catch (error: any) {
        console.error('Error fetching ad detail:', error);
        
        let errorMessage = "Failed to fetch ad details";
        if (error.response?.status === 401) {
          errorMessage = "Authentication failed. Please log in again.";
        } else if (error.response?.status === 404) {
          errorMessage = "Ad not found. It may have been deleted.";
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
    
    fetchAdDetail();
  }, [id, token]);

  // Fetch ad metrics
  useEffect(() => {
    const fetchAdMetrics = async () => {
      if (!adAnalysis) return;
      
      setMetricsLoading(true);
      setMetricsError(null);
      
      try {
        // Get all possible IDs that could identify this ad
        const adId = adAnalysis.ad_id || '';
        const videoId = adAnalysis.video_id || '';
        const mongoId = adAnalysis._id || '';
        const campaignId = adAnalysis.campaign_id || '';
        
        console.log('Possible IDs to match:', { 
          adId, 
          videoId, 
          mongoId, 
          campaignId 
        });
        
        // Fetch metrics from the by-ad endpoint with the date range
        const response = await axios.get('/api/v1/ad-metrics/by-ad/', {
          params: {
            start_date: startDate,
            end_date: endDate,
            force_refresh: false
          },
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        
        if (response.data && response.data.ad_metrics) {
          console.log('All metrics data:', response.data.ad_metrics);
          
          // Find all potential matches using any available ID
          const filteredMetrics = response.data.ad_metrics.filter((metric: AdMetric) => {
            // Log each metric's IDs for debugging
            console.log('Checking metric:', {
              metricAdId: metric.ad_id,
              metricCampaignId: metric.campaign_id
            });
            
            // Check for any matching ID
            return (
              (adId && metric.ad_id === adId) ||
              (videoId && metric.ad_id === videoId) ||
              (mongoId && metric.ad_id === mongoId) ||
              (campaignId && metric.campaign_id === campaignId) ||
              // Also check if ad names match (as fallback)
              (adAnalysis.ad_title && metric.ad_name === adAnalysis.ad_title)
            );
          });
          
          console.log(`Filtered metrics count: ${filteredMetrics.length}`);
          
          if (filteredMetrics.length > 0) {
            console.log('Found metrics for this ad:', filteredMetrics);
            setAdMetrics(filteredMetrics);
          } else {
            // If no exact matches, check if any metrics might be related
            // This is a fallback approach that looks for partial matches
            console.log('No exact matches found, looking for partial matches');
            
            // Try using the first part of the campaign ID as a partial match
            if (campaignId) {
              const partialMatchMetrics = response.data.ad_metrics.filter((metric: AdMetric) => {
                return metric.campaign_id && metric.campaign_id.includes(campaignId.substring(0, 10));
              });
              
              if (partialMatchMetrics.length > 0) {
                console.log('Found metrics using partial campaign ID match:', partialMatchMetrics);
                setAdMetrics(partialMatchMetrics);
                return;
              }
            }
            
            // If still no matches, and we have unique ads data, use the ad with most similar name
            if (response.data.unique_ads && response.data.unique_ads.length > 0 && adAnalysis.ad_title) {
              // Find an ad with a similar name
              const similarAd = response.data.unique_ads.find((ad: any) => 
                ad.ad_name.toLowerCase().includes(adAnalysis.ad_title?.toLowerCase() || '') ||
                (adAnalysis.ad_title?.toLowerCase() || '').includes(ad.ad_name.toLowerCase())
              );
              
              if (similarAd) {
                console.log('Found similar ad:', similarAd);
                const similarAdMetrics = response.data.ad_metrics.filter((metric: AdMetric) => 
                  metric.ad_id === similarAd.ad_id
                );
                
                if (similarAdMetrics.length > 0) {
                  console.log('Using metrics from similar ad:', similarAdMetrics);
                  setAdMetrics(similarAdMetrics);
                  return;
                }
              }
            }
            
            // Last resort: use all metrics from campaign if available
            if (campaignId) {
              const campaignMetrics = response.data.ad_metrics.filter((metric: AdMetric) =>
                metric.campaign_id === campaignId
              );
              
              if (campaignMetrics.length > 0) {
                console.log('Using all metrics from same campaign:', campaignMetrics);
                setAdMetrics(campaignMetrics);
                return;
              }
            }
            
            // If we've exhausted all options and can't find any related metrics
            console.log('No metrics found for this ad with any matching method');
            setMetricsError("No metrics data available for this specific ad");
          }
        } else {
          setMetricsError("No metrics data available");
        }
      } catch (error: any) {
        console.error('Error fetching ad metrics:', error);
        
        let errorMessage = "Failed to fetch ad metrics";
        if (error.response?.status === 401) {
          errorMessage = "Authentication failed. Please log in again.";
        } else if (error.response?.data?.detail) {
          errorMessage = error.response.data.detail;
        }
        
        setMetricsError(errorMessage);
      } finally {
        setMetricsLoading(false);
      }
    };
    
    fetchAdMetrics();
  }, [adAnalysis, token, startDate, endDate]);

  // Handle forecast toggle
  const handleForecastToggle = async (enabled: boolean) => {
    setShowForecast(enabled);
    
    if (enabled && Object.keys(forecastData).length === 0 && adMetrics.length > 0) {
      setForecastLoading(true);
      console.log('Generating forecast for ad:', adAnalysis);
      
      try {
        // Try multiple possible IDs to identify this ad
        // First check adMetrics - if available, use the first metric's ad_id
        let adId = '';
        
        if (adMetrics.length > 0 && adMetrics[0].ad_id) {
          adId = adMetrics[0].ad_id;
          console.log('Using ad_id from metrics:', adId);
        } else {
          // Try all possible IDs from the ad analysis object
          const possibleIds = [
            adAnalysis?.ad_id,        // Try ad_id first
            adAnalysis?.video_id,     // Then video_id 
            adAnalysis?._id,          // Then MongoDB _id
            id                        // Finally the route parameter id
          ];
          
          // Use the first non-empty ID
          adId = possibleIds.find(id => id && id.length > 0) || '';
          console.log('Using alternate ID for forecast:', adId);
        }
        
        // If no ID can be found from the metrics or ad analysis, try a direct call with the URL parameter as a last resort
        if (!adId && id) {
          console.log('Trying direct API call with URL parameter ID:', id);
          try {
            // Make a direct call using the URL parameter
            const directResponse = await axios.get(`/api/v1/predictions/ad/${id}`, {
              params: {
                start_date: startDate,
                end_date: endDate,
                days_to_predict: 14,
                use_time_series: true
              },
              headers: {
                Authorization: `Bearer ${token}`
              }
            });
            
            if (directResponse.data && directResponse.data.success) {
              console.log('Direct API call successful with URL parameter ID');
              // Process this response
              let predictionData = directResponse.data.predictions;
              
              // Handle different possible structures in the response
              if (!Array.isArray(predictionData) && directResponse.data.ad_id && Array.isArray(directResponse.data.predictions?.predictions)) {
                console.log('Found nested predictions structure, extracting inner predictions array');
                predictionData = directResponse.data.predictions.predictions;
              }
              
              // If we still don't have an array, check if historical data is available as fallback
              if (!Array.isArray(predictionData) && Array.isArray(directResponse.data.historical)) {
                console.log('No predictions found, using historical data as fallback');
                predictionData = directResponse.data.historical;
              }
              
              console.log('Prediction data array from direct call:', predictionData);
              
              if (!predictionData || predictionData.length === 0) {
                console.warn('No prediction data received from direct API call');
                toast({
                  variant: "destructive",
                  title: "Forecast Error",
                  description: "No forecast data available for this ad"
                });
                setForecastLoading(false);
                return;
              }
              
              const forecastMetrics: Record<string, ForecastData> = {};
              
              // Metrics we want to extract
              const metricsToExtract = ['spend', 'revenue', 'impressions', 'clicks', 'purchases', 'ctr', 'cpc', 'cpm', 'roas'];
              
              // Check which metrics are available in the data
              const availableMetrics = new Set<string>();
              predictionData.forEach((prediction: any) => {
                Object.keys(prediction).forEach(key => {
                  if (metricsToExtract.includes(key)) {
                    availableMetrics.add(key);
                  }
                });
              });
              
              console.log('Available metrics from direct call:', Array.from(availableMetrics));
              
              // Initialize containers for metrics
              metricsToExtract.forEach(metric => {
                forecastMetrics[metric] = {
                  dates: [],
                  values: [],
                  metric
                };
              });
              
              // Extract prediction data
              predictionData.forEach((prediction: any, index: number) => {
                console.log('Processing prediction day:', prediction);
                
                // Make sure we have a date
                let predictionDate = prediction.date;
                
                // If no date is available, generate one
                if (!predictionDate) {
                  const baseDate = new Date();
                  baseDate.setDate(baseDate.getDate() + index);
                  predictionDate = formatDate(baseDate);
                }
                
                metricsToExtract.forEach(metric => {
                  if (metric in prediction) {
                    forecastMetrics[metric].dates.push(predictionDate);
                    forecastMetrics[metric].values.push(prediction[metric]);
                  } else {
                    // If metric is missing, add a fallback value
                    let fallbackValue = 0;
                    
                    if (['roas', 'ctr', 'cpc', 'cpm'].includes(metric) && forecastMetrics[metric].values.length > 0) {
                      // For rate metrics, use the previous day's value as fallback
                      fallbackValue = forecastMetrics[metric].values[forecastMetrics[metric].values.length - 1];
                    }
                    
                    forecastMetrics[metric].dates.push(predictionDate);
                    forecastMetrics[metric].values.push(fallbackValue);
                  }
                });
              });
              
              // After processing all predictions, ensure all metrics have at least some data
              metricsToExtract.forEach(metric => {
                if (forecastMetrics[metric].dates.length === 0 && adMetrics.length > 0) {
                  // If this metric has no forecasted data but we have historical data,
                  // create simple extrapolated data based on the most recent historical values
                  
                  // Sort metrics by date (most recent last)
                  const sortedMetrics = [...adMetrics].sort((a, b) => 
                    new Date(a.date).getTime() - new Date(b.date).getTime()
                  );
                  
                  // Get up to last 7 days of historical data for this metric
                  const recentMetrics = sortedMetrics.slice(-7);
                  
                  if (recentMetrics.length > 0) {
                    // Calculate average daily change
                    let sum = 0;
                    let count = 0;
                    
                    // Get the average value
                    recentMetrics.forEach(m => {
                      if (metric in m) {
                        sum += m[metric as keyof AdMetric] as number;
                        count++;
                      }
                    });
                    
                    const avgValue = count > 0 ? sum / count : 0;
                    
                    // Generate dates for the next 14 days
                    const lastDate = new Date(sortedMetrics[sortedMetrics.length - 1].date);
                    
                    for (let i = 1; i <= 14; i++) {
                      const nextDate = new Date(lastDate);
                      nextDate.setDate(lastDate.getDate() + i);
                      const formattedDate = formatDate(nextDate);
                      
                      // Add the date and forecasted value
                      forecastMetrics[metric].dates.push(formattedDate);
                      forecastMetrics[metric].values.push(avgValue);
                    }
                    
                    console.log(`Generated fallback forecast for ${metric} based on historical average:`, forecastMetrics[metric]);
                  }
                }
              });
              
              console.log('Forecast metrics from direct call:', forecastMetrics);
              setForecastData(forecastMetrics);
              setForecastLoading(false);
              return; // Return after successful processing
            }
          } catch (error) {
            console.error('Direct API call failed:', error);
          }
        }
        
        // Show more detailed error if we still haven't found an ID
        if (!adId) {
          console.error('No usable ID found for forecast. Available data:', {
            'URL parameter id': id,
            'adAnalysis': adAnalysis,
            'adMetrics': adMetrics
          });
          
          toast({
            variant: "destructive",
            title: "Forecast Error",
            description: "Unable to forecast: Ad ID not found"
          });
          setForecastLoading(false);
          return;
        }
        
        console.log(`Calling prediction API for ad ID: ${adId}`);
        
        // Call the correct prediction API endpoint
        const response = await axios.get(`/api/v1/predictions/ad/${adId}`, {
          params: {
            start_date: startDate,
            end_date: endDate,
            days_to_predict: 14, // Forecast for next 14 days
            use_time_series: true
          },
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        
        console.log('Full prediction API response:', response);

        if (response.data && response.data.success) {
          console.log('Prediction data received:', response.data);
          
          // Transform the predictions into the format expected by our charts
          // Handle different possible structures in the API response
          let predictionData = response.data.predictions;
          
          // If the API returns nested predictions, handle that case
          if (!Array.isArray(predictionData) && response.data.ad_id && Array.isArray(response.data.predictions?.predictions)) {
            console.log('Found nested predictions structure, extracting inner predictions array');
            predictionData = response.data.predictions.predictions;
          }
          
          // If we still don't have an array, check if historical data is available as fallback
          if (!Array.isArray(predictionData) && Array.isArray(response.data.historical)) {
            console.log('No predictions found, using historical data as fallback');
            predictionData = response.data.historical;
          }
          
          console.log('Prediction data array:', predictionData);
          
          if (!predictionData || predictionData.length === 0) {
            console.warn('No prediction data received from API');
            toast({
              variant: "destructive",
              title: "Forecast Error",
              description: "No forecast data available for this ad"
            });
            setForecastLoading(false);
            return;
          }
          
          const forecastMetrics: Record<string, ForecastData> = {};
          
          // Metrics we want to extract from predictions
          const metricsToExtract = ['spend', 'revenue', 'impressions', 'clicks', 'purchases', 'ctr', 'cpc', 'cpm', 'roas'];
          
          // Check which metrics are available in the prediction data
          const availableMetrics = new Set<string>();
          predictionData.forEach((prediction: any) => {
            Object.keys(prediction).forEach(key => {
              if (metricsToExtract.includes(key)) {
                availableMetrics.add(key);
              }
            });
          });
          
          console.log('Available metrics in prediction data:', Array.from(availableMetrics));
          
          // Initialize containers for each available metric
          metricsToExtract.forEach(metric => {
            forecastMetrics[metric] = {
              dates: [],
              values: [],
              metric
            };
          });
          
          // Extract prediction data for each metric
          predictionData.forEach((prediction: any, index: number) => {
            console.log('Processing prediction day:', prediction);
            
            // Make sure we have a date
            let predictionDate = prediction.date;
            
            // If no date is available, generate one based on index
            if (!predictionDate) {
              const baseDate = new Date();
              baseDate.setDate(baseDate.getDate() + index);
              predictionDate = formatDate(baseDate);
            }
            
            metricsToExtract.forEach(metric => {
              if (metric in prediction) {
                forecastMetrics[metric].dates.push(predictionDate);
                forecastMetrics[metric].values.push(prediction[metric]);
              } else {
                // If metric is missing, add a fallback value
                let fallbackValue = 0;
                
                if (['roas', 'ctr', 'cpc', 'cpm'].includes(metric) && forecastMetrics[metric].values.length > 0) {
                  // For rate metrics, use the previous day's value as fallback
                  fallbackValue = forecastMetrics[metric].values[forecastMetrics[metric].values.length - 1];
                }
                
                forecastMetrics[metric].dates.push(predictionDate);
                forecastMetrics[metric].values.push(fallbackValue);
              }
            });
          });
          
          // After processing all predictions, ensure all metrics have at least some data
          metricsToExtract.forEach(metric => {
            if (forecastMetrics[metric].dates.length === 0 && adMetrics.length > 0) {
              // If this metric has no forecasted data but we have historical data,
              // create simple extrapolated data based on the most recent historical values
              
              // Sort metrics by date (most recent last)
              const sortedMetrics = [...adMetrics].sort((a, b) => 
                new Date(a.date).getTime() - new Date(b.date).getTime()
              );
              
              // Get up to last 7 days of historical data for this metric
              const recentMetrics = sortedMetrics.slice(-7);
              
              if (recentMetrics.length > 0) {
                // Calculate average daily change
                let sum = 0;
                let count = 0;
                
                // Get the average value
                recentMetrics.forEach(m => {
                  if (metric in m) {
                    sum += m[metric as keyof AdMetric] as number;
                    count++;
                  }
                });
                
                const avgValue = count > 0 ? sum / count : 0;
                
                // Generate dates for the next 14 days
                const lastDate = new Date(sortedMetrics[sortedMetrics.length - 1].date);
                
                for (let i = 1; i <= 14; i++) {
                  const nextDate = new Date(lastDate);
                  nextDate.setDate(lastDate.getDate() + i);
                  const formattedDate = formatDate(nextDate);
                  
                  // Add the date and forecasted value
                  forecastMetrics[metric].dates.push(formattedDate);
                  forecastMetrics[metric].values.push(avgValue);
                }
                
                console.log(`Generated fallback forecast for ${metric} based on historical average:`, forecastMetrics[metric]);
              }
            }
          });
          
          console.log('Forecast metrics from prediction API:', forecastMetrics);
          
          // Set the formatted forecast data
          setForecastData(forecastMetrics);
        } else {
          toast({
            variant: "destructive",
            title: "Forecast Error",
            description: response.data?.message || "Failed to generate forecast data"
          });
        }
      } catch (error: any) {
        console.error('Error generating forecast:', error);
        toast({
          variant: "destructive",
          title: "Forecast Error",
          description: error.response?.data?.detail || "Failed to generate forecast data"
        });
      } finally {
        setForecastLoading(false);
      }
    }
  };

  // Format values for charts
  const formatMoneyValue = (value: number) => {
    return `Rs.${value.toLocaleString('en-PK', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  };
  
  const formatPercentage = (value: number) => {
    // Simply add a % symbol without changing the value
    return `${value}%`;
  };

  // Updated getChartData to include forecast data and handle CTR correctly
  const getChartData = (metric: string) => {
    if (!adMetrics || adMetrics.length === 0) return { chartData: [], layout: {} };
    
    const sortedMetrics = [...adMetrics].sort((a, b) => 
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    
    let yLabel = '';
    let valueFormatter = (val: number) => val.toString();
    
    switch (metric) {
      case 'spend':
        yLabel = 'Ad Spend (Rs.)';
        valueFormatter = (val: number) => formatMoneyValue(val);
        break;
      case 'revenue':
        yLabel = 'Revenue (Rs.)';
        valueFormatter = (val: number) => formatMoneyValue(val);
        break;
      case 'roas':
        yLabel = 'Return on Ad Spend';
        valueFormatter = (val: number) => val.toFixed(2);
        break;
      case 'ctr':
        yLabel = 'Click-Through Rate';
        valueFormatter = (val: number) => `${val}%`;  // Display raw value with % sign
        break;
      case 'cpc':
        yLabel = 'Cost per Click (Rs.)';
        valueFormatter = (val: number) => formatMoneyValue(val);
        break;
      case 'cpm':
        yLabel = 'Cost per 1,000 Impressions (Rs.)';
        valueFormatter = (val: number) => formatMoneyValue(val);
        break;
      case 'impressions':
        yLabel = 'Impressions';
        valueFormatter = (val: number) => val.toLocaleString();
        break;
      case 'clicks':
        yLabel = 'Clicks';
        valueFormatter = (val: number) => val.toLocaleString();
        break;
      case 'purchases':
        yLabel = 'Purchases';
        valueFormatter = (val: number) => val.toLocaleString();
        break;
      default:
        yLabel = 'Value';
    }
    
    // Create the main data series
    const mainSeries = {
      x: sortedMetrics.map(m => m.date),
      y: sortedMetrics.map(m => m[metric as keyof AdMetric] as number),
      type: 'scatter',
      mode: 'lines+markers',
      name: yLabel,
      line: { 
        color: '#4c6ef5', 
        width: 2
      },
      marker: { 
        size: 6,
        color: '#4c6ef5'
      },
      hovertemplate: `%{x}<br>${yLabel}: ${metric === 'ctr' ? '%{y}%' : '%{y}'}<extra></extra>`
    };
    
    // Create chart data array starting with the main series
    const chartData = [mainSeries];
    
    // Add forecast data if available and enabled
    if (showForecast && forecastData[metric]) {
      const forecast = forecastData[metric];
      
      // Include forecast data starting from the day after the last actual date
      chartData.push({
        x: forecast.dates,
        y: forecast.values,
        type: 'scatter',
        mode: 'lines',
        name: `${yLabel} (Forecast)`,
        line: { 
          color: '#ff6b6b', 
          width: 2,
          dash: 'dashdot'
        } as any,
        marker: {
          size: 5,
          color: '#ff6b6b'
        },
        hovertemplate: `%{x}<br>${yLabel} (Forecast): ${metric === 'ctr' ? '%{y}%' : '%{y}'}<extra></extra>`
      });
    }
    
    const layout = {
      autosize: true,
      title: {
        text: yLabel,
        font: {
          size: 16
        }
      },
      xaxis: {
        title: 'Date',
        showgrid: true,
        gridcolor: '#f0f0f0'
      },
      yaxis: {
        title: yLabel,
        showgrid: true,
        gridcolor: '#f0f0f0',
        tickformat: metric === 'ctr' ? undefined : undefined, // No special formatting for CTR
      },
      margin: { l: 50, r: 20, t: 50, b: 50 },
      hovermode: 'closest' as 'closest',
      paper_bgcolor: 'white',
      plot_bgcolor: 'white',
      legend: {
        orientation: 'h' as 'h',
        yanchor: 'bottom' as 'bottom',
        y: -0.2,
        xanchor: 'center' as 'center',
        x: 0.5
      }
    };
    
    return { chartData, layout };
  };

  const goBack = () => {
    navigate('/ad-analysis');
  };

  const startEditing = (field: 'product' | 'product_type', currentValue: string) => {
    setEditingFields(prev => ({
      ...prev,
      [field]: true
    }));
    setEditValues(prev => ({
      ...prev,
      [field]: currentValue || ''
    }));
  };

  const cancelEditing = (field: 'product' | 'product_type') => {
    setEditingFields(prev => ({
      ...prev,
      [field]: false
    }));
    setEditValues(prev => ({
      ...prev,
      [field]: undefined
    }));
  };

  const updateAdAnalysis = async (field: 'product' | 'product_type', newValue: string) => {
    if (!adAnalysis) return;

    try {
      const updateData = {
        [field]: newValue.trim()
      };

      const response = await axios.patch(`/api/v1/ad-analysis/${adAnalysis._id}`, updateData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.data.success && response.data.updated_analysis) {
        // Update the local state with the updated analysis
        setAdAnalysis(prev => prev ? {
          ...prev,
          ad_analysis: {
            ...prev.ad_analysis,
            [field]: newValue.trim()
          }
        } : null);

        // Clear editing state
        cancelEditing(field);

        toast({
          title: "Success",
          description: `${field === 'product' ? 'Product' : 'Product Type'} updated successfully.`
        });
      }
      
    } catch (error: any) {
      console.error('Error updating ad analysis:', error);
      
      let errorMessage = "Failed to update analysis";
      if (error.response?.status === 404) {
        errorMessage = "Ad analysis not found";
      } else if (error.response?.status === 401) {
        errorMessage = "Authentication failed. Please log in again.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }
      
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage
      });
    }
  };

  const handleSaveEdit = (field: 'product' | 'product_type') => {
    const newValue = editValues[field] || '';
    updateAdAnalysis(field, newValue);
  };

  // Helper component for editable fields
  const EditableField = ({ 
    field, 
    value, 
    label 
  }: { 
    field: 'product' | 'product_type'; 
    value: string; 
    label: string; 
  }) => {
    const isEditing = editingFields[field] || false;
    const editValue = editValues[field] || '';

    if (isEditing) {
      return (
        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="font-bold text-gray-800">{label}</p>
            <div className="flex items-center space-x-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                onClick={() => handleSaveEdit(field)}
                title="Save changes"
              >
                <Check className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-gray-600 hover:text-gray-700 hover:bg-gray-50"
                onClick={() => cancelEditing(field)}
                title="Cancel editing"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <Input
            value={editValue}
            onChange={(e) => setEditValues(prev => ({
              ...prev,
              [field]: e.target.value
            }))}
            className="h-8 text-sm"
            placeholder={`Enter ${label.toLowerCase()}`}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSaveEdit(field);
              } else if (e.key === 'Escape') {
                cancelEditing(field);
              }
            }}
            autoFocus
          />
        </div>
      );
    }

    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="font-bold text-gray-800">{label}</p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50"
            onClick={() => startEditing(field, value)}
            title={`Edit ${label.toLowerCase()}`}
          >
            <Edit3 className="h-3 w-3" />
          </Button>
        </div>
        <p className="text-base cursor-pointer" onClick={() => startEditing(field, value)}>
          {value || 'N/A'}
        </p>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col h-screen">
        <div className="bg-background py-4 px-8 border-b shadow-sm">
          <div className="container mx-auto flex items-center">
            <Button variant="ghost" className="mr-4" onClick={goBack}>
              <ChevronLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <h1 className="text-3xl font-bold">Ad Detail</h1>
          </div>
        </div>
        <div className="flex-1 flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      </div>
    );
  }

  if (error || !adAnalysis) {
    return (
      <div className="flex flex-col h-screen">
        <div className="bg-background py-4 px-8 border-b shadow-sm">
          <div className="container mx-auto flex items-center">
            <Button variant="ghost" className="mr-4" onClick={goBack}>
              <ChevronLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <h1 className="text-3xl font-bold">Ad Detail</h1>
          </div>
        </div>
        <div className="flex-1 flex flex-col justify-center items-center">
          <p className="text-lg text-destructive mb-4">{error || "Ad not found"}</p>
          <Button onClick={goBack} variant="outline">Go Back</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <div className="bg-background py-4 px-8 border-b shadow-sm">
        <div className="container mx-auto flex items-center">
          <Button variant="ghost" className="mr-4" onClick={goBack}>
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <h1 className="text-3xl font-bold">Ad Detail</h1>
        </div>
      </div>
      
      <div className="h-[calc(100vh-5rem)] overflow-auto py-6 px-8 pb-12">
        <div className="container mx-auto max-w-5xl mb-12">
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl">{adAnalysis.ad_title || 'Untitled Ad'}</CardTitle>
                  <CardDescription className="text-base mt-1">
                    Campaign: {adAnalysis.campaign_name || 'Unknown Campaign'}
                  </CardDescription>
                  <CardDescription className="mt-1">
                    Ad Set: {adAnalysis.adset_name || 'Unknown Ad Set'}
                  </CardDescription>
                </div>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                  adAnalysis.ad_status === 'ACTIVE' 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {adAnalysis.ad_status || 'Unknown'}
                </span>
              </div>
              {adAnalysis.ad_message && (
                <div className="mt-4 text-base whitespace-pre-line bg-gray-50 p-4 rounded-md">
                  {linkifyText(adAnalysis.ad_message)}
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Media (if available) */}
              {adAnalysis.video_url && (
                <div className="flex justify-center">
                  <video 
                    controls 
                    src={adAnalysis.video_url} 
                    className="rounded-md shadow-md max-w-full h-auto max-h-[400px]" 
                    preload="metadata"
                  />
                </div>
              )}
              
              {/* Analysis Results */}
              <div>
                <h3 className="text-xl font-bold mb-3">Analysis Results</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-gray-50 p-4 rounded-md">
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Hook</p>
                    <p className="text-base">{adAnalysis.ad_analysis?.hook || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Tone</p>
                    <p className="text-base">{adAnalysis.ad_analysis?.tone || 'N/A'}</p>
                  </div>
                  <EditableField
                    field="product"
                    value={adAnalysis.ad_analysis?.product || ''}
                    label="Product"
                  />
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Power Phrases</p>
                    <p className="text-base">{adAnalysis.ad_analysis?.power_phrases || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Visual</p>
                    <p className="text-base">{adAnalysis.ad_analysis?.visual || 'N/A'}</p>
                  </div>
                  <EditableField
                    field="product_type"
                    value={adAnalysis.ad_analysis?.product_type || ''}
                    label="Product Type"
                  />
                </div>
              </div>
              
              {/* Targeting Information */}
              <div>
                <h3 className="text-xl font-bold mb-3">Targeting Information</h3>
                <div className="bg-gray-50 p-4 rounded-md">
                  {renderTargetingFields(adAnalysis.adset_targeting)}
                </div>
              </div>

              {/* Additional Information */}
              {(adAnalysis.audio_description || adAnalysis.video_description) && (
                <div>
                  <h3 className="text-xl font-bold mb-3">Additional Information</h3>
                  <div className="space-y-4 bg-gray-50 p-4 rounded-md">
                    {adAnalysis.audio_description && (
                      <div>
                        <p className="font-bold text-gray-800 mb-1">Audio Description</p>
                        <p className="text-base">{adAnalysis.audio_description}</p>
                      </div>
                    )}
                    {adAnalysis.video_description && (
                      <div>
                        <p className="font-bold text-gray-800 mb-1">Video Description</p>
                        <p className="text-base">{adAnalysis.video_description}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Metadata */}
              <div>
                <h3 className="text-xl font-bold mb-3">Metadata</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-gray-50 p-4 rounded-md">
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Ad ID</p>
                    <p className="text-base break-all">{adAnalysis._id}</p>
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Campaign ID</p>
                    <p className="text-base break-all">{adAnalysis.campaign_id || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Ad Set ID</p>
                    <p className="text-base break-all">{adAnalysis.adset_id || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Video ID</p>
                    <p className="text-base break-all">{adAnalysis.video_id || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="font-bold text-gray-800 mb-1">Created</p>
                    <p className="text-base">{new Date(adAnalysis.created_at).toLocaleString()}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Ad Metrics Section */}
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl">Ad Performance Metrics</CardTitle>
                  <CardDescription>
                    Metrics for this ad from {startDate} to {endDate}
                  </CardDescription>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="forecast-toggle"
                    checked={showForecast}
                    onCheckedChange={handleForecastToggle}
                    disabled={metricsLoading || adMetrics.length === 0}
                  />
                  <Label htmlFor="forecast-toggle">Forecast</Label>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {metricsLoading ? (
                <div className="flex justify-center items-center h-[400px]">
                  <Loader2 className="h-8 w-8 animate-spin" />
                </div>
              ) : forecastLoading ? (
                <div className="flex justify-center items-center h-[400px]">
                  <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                    <p>Generating forecast...</p>
                  </div>
                </div>
              ) : metricsError ? (
                <div className="text-center py-8">
                  <p className="text-destructive mb-2">{metricsError}</p>
                  <p className="text-sm text-muted-foreground">
                    This could be because the ad hasn't run yet or metrics data isn't available.
                  </p>
                </div>
              ) : adMetrics.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">No metrics data available for this ad</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <Tabs defaultValue="spend" value={selectedMetricTab} onValueChange={setSelectedMetricTab}>
                    <TabsList className="grid grid-cols-3 md:grid-cols-9 mb-4">
                      <TabsTrigger value="spend">Spend</TabsTrigger>
                      <TabsTrigger value="revenue">Revenue</TabsTrigger>
                      <TabsTrigger value="roas">ROAS</TabsTrigger>
                      <TabsTrigger value="impressions">Impressions</TabsTrigger>
                      <TabsTrigger value="clicks">Clicks</TabsTrigger>
                      <TabsTrigger value="ctr">CTR</TabsTrigger>
                      <TabsTrigger value="cpc">CPC</TabsTrigger>
                      <TabsTrigger value="cpm">CPM</TabsTrigger>
                      <TabsTrigger value="purchases">Purchases</TabsTrigger>
                    </TabsList>
                    
                    {['spend', 'revenue', 'roas', 'impressions', 'clicks', 'ctr', 'cpc', 'cpm', 'purchases'].map(metric => {
                      const chartInfo = getChartData(metric);
                      return (
                        <TabsContent key={metric} value={metric}>
                          <div className="h-[400px]">
                            {adMetrics.length > 0 && (
                              <PlotlyLineChart
                                data={chartInfo.chartData}
                                layout={chartInfo.layout}
                              />
                            )}
                          </div>
                        </TabsContent>
                      );
                    })}
                  </Tabs>
                  
                  {/* Summary metrics */}
                  <div className="grid grid-cols-3 md:grid-cols-5 gap-4 pt-4 mt-4 border-t">
                    {adMetrics.length > 0 && (
                      <>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Total Spend</p>
                          <p className="text-xl font-semibold">
                            {formatMoneyValue(adMetrics.reduce((sum, m) => sum + m.spend, 0))}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Total Revenue</p>
                          <p className="text-xl font-semibold">
                            {formatMoneyValue(adMetrics.reduce((sum, m) => sum + m.revenue, 0))}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Avg. ROAS</p>
                          <p className="text-xl font-semibold">
                            {(adMetrics.reduce((sum, m) => sum + m.revenue, 0) / 
                              adMetrics.reduce((sum, m) => sum + m.spend, 0) || 0).toFixed(2)}x
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Total Clicks</p>
                          <p className="text-xl font-semibold">
                            {adMetrics.reduce((sum, m) => sum + m.clicks, 0).toLocaleString()}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Total Purchases</p>
                          <p className="text-xl font-semibold">
                            {adMetrics.reduce((sum, m) => sum + m.purchases, 0).toLocaleString()}
                          </p>
                        </div>
                        
                        {/* Additional summary row for CTR and impressions */}
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Avg. CTR</p>
                          <p className="text-xl font-semibold">
                            {(adMetrics.reduce((sum, m) => sum + m.ctr, 0) / adMetrics.length || 0)}%
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">Total Impressions</p>
                          <p className="text-xl font-semibold">
                            {adMetrics.reduce((sum, m) => sum + m.impressions, 0).toLocaleString()}
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default AdDetail; 