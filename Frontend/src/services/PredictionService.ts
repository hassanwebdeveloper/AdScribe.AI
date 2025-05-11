import axios from 'axios';

interface PredictionMetric {
  date: string;
  ad_id: string;
  ad_name?: string;
  roas: number;
  ctr: number;
  cpc: number;
  cpm: number;
  conversions: number;
  revenue: number;
  spend: number;
}

interface AdPrediction {
  ad_id: string;
  predictions: PredictionMetric[];
  success: boolean;
  message?: string;
}

interface BestAdPrediction {
  ad_id: string;
  ad_name: string;
  ad_title?: string;
  campaign_name?: string;
  adset_name?: string;
  average_metrics: {
    roas: number;
    ctr: number;
    cpc: number;
    cpm: number;
    conversions: number;
    revenue: number;
  };
}

interface AllAdsPredictionResponse {
  success: boolean;
  message?: string;
  predictions: AdPrediction[];
  best_ad: BestAdPrediction | null;
}

interface BestAdResponse {
  success: boolean;
  message: string;
  best_ad?: BestAdPrediction;
}

interface PredictionOptions {
  useTimeSeries?: boolean;
}

class PredictionService {
  /**
   * Predict metrics for a specific ad
   */
  async predictAdMetrics(
    adId: string,
    startDate: string,
    endDate: string,
    daysToPredict: number = 7,
    options: PredictionOptions = { useTimeSeries: true }
  ): Promise<AdPrediction> {
    try {
      const response = await axios.get(`/api/v1/predictions/ad/${adId}`, {
        params: {
          start_date: startDate,
          end_date: endDate,
          days_to_predict: daysToPredict,
          use_time_series: options.useTimeSeries
        },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      return response.data;
    } catch (error) {
      console.error('Error predicting ad metrics:', error);
      return {
        ad_id: adId,
        predictions: [],
        success: false,
        message: 'Failed to predict metrics for this ad'
      };
    }
  }
  
  /**
   * Predict metrics for all ads and find the best performing one
   */
  async predictAllAdsMetrics(
    startDate: string,
    endDate: string,
    daysToPredict: number = 7,
    options: PredictionOptions = { useTimeSeries: true }
  ): Promise<AllAdsPredictionResponse> {
    try {
      const response = await axios.get('/api/v1/predictions/all-ads', {
        params: {
          start_date: startDate,
          end_date: endDate,
          days_to_predict: daysToPredict,
          use_time_series: options.useTimeSeries
        },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      return response.data;
    } catch (error) {
      console.error('Error predicting all ads metrics:', error);
      return {
        success: false,
        message: 'Failed to predict metrics for ads',
        predictions: [],
        best_ad: null
      };
    }
  }
  
  /**
   * Gets the best performing ad prediction based on historical data
   * @param startDate Start date in YYYY-MM-DD format
   * @param endDate End date in YYYY-MM-DD format
   * @param daysToPredict Number of days to predict
   * @param options Optional parameters
   * @returns Promise with the best ad prediction
   */
  async getBestPerformingAd(
    startDate: string,
    endDate: string,
    daysToPredict: number = 7,
    options: { useTimeSeries?: boolean } = {}
  ): Promise<BestAdResponse> {
    try {
      // API endpoint for best ad prediction
      const endpoint = `/api/v1/predictions/best-ad`;
      
      // Call the API with parameters
      const response = await axios.get(endpoint, {
        params: {
          start_date: startDate,
          end_date: endDate,
          days_to_predict: daysToPredict,
          use_time_series: options.useTimeSeries || false
        },
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      // Check if the response has the expected structure
      if (response.data && response.data.best_ad) {
        return {
          success: true,
          message: response.data.message || 'Successfully predicted best ad',
          best_ad: response.data.best_ad
        };
      } 
      
      // Handle case where API returns a welcome message instead of predictions
      if (response.data && response.data.message === "Welcome to AdScribe AI API") {
        return {
          success: false,
          message: "The prediction service is not available at this time. Please try again later."
        };
      }
      
      // Handle other unexpected API responses
      return {
        success: false,
        message: response.data?.message || 'No best ad prediction available'
      };
    } catch (error) {
      console.error('Error fetching best ad prediction:', error);
      
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Error fetching prediction'
      };
    }
  }
}

export default new PredictionService();
export type { PredictionMetric, AdPrediction, BestAdPrediction, AllAdsPredictionResponse, BestAdResponse, PredictionOptions }; 