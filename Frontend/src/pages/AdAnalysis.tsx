import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, RefreshCw, History, Play, Trash2, Edit3, Check, X, AlertTriangle } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { prerequisiteService } from '@/services/prerequisiteService';
import { backgroundJobService, BackgroundJob, JobStatusUpdate } from '@/services/backgroundJobService';
import JobProgress from '@/components/JobProgress';

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
  const [error, setError] = useState<string | null>(null);
  const [isCollecting, setIsCollecting] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  
  // Background job states
  const [currentJob, setCurrentJob] = useState<BackgroundJob | null>(null);
  const [jobHistory, setJobHistory] = useState<BackgroundJob[]>([]);
  const [showJobHistory, setShowJobHistory] = useState(false);
  
  // Editing states
  const [editingFields, setEditingFields] = useState<{[key: string]: {product?: boolean, product_type?: boolean}}>({});
  const [editValues, setEditValues] = useState<{[key: string]: {product?: string, product_type?: string}}>({});
  
  const { token } = useAuth();
  const { toast } = useToast();

  // Check if data collection is active
  useEffect(() => {
    const checkCollectionStatus = async () => {
      try {
        console.log('Checking collection status...');
        const response = await axios.get('/api/v1/ad-analysis/collection-status', {
          headers: { Authorization: `Bearer ${token}` }
        });
        console.log('Collection status response:', response.data);
        
        // Updated to use the correct response format
        if (response.data.status !== undefined) {
          // Use the database status (status) instead of is_running
          setIsCollecting(response.data.status);
          console.log('Set collection status to:', response.data.status);
        } else if (response.data.is_collecting !== undefined) {
          // Backward compatibility for legacy API response
          setIsCollecting(response.data.is_collecting);
          console.log('Set collection status to (legacy):', response.data.is_collecting);
        }
      } catch (error) {
        console.error('Error checking collection status:', error);
      }
    };
    checkCollectionStatus();
  }, [token]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      console.log('AdAnalysis component unmounting, cleaning up background job polling');
      backgroundJobService.stopAllPolling();
    };
  }, []);

  // Load job history and check for running jobs on mount
  useEffect(() => {
    console.log('AdAnalysis component mounted, loading job history');
    loadJobHistory();
    fetchAdAnalyses();
  }, []);

  // Periodic cleanup of stale polling intervals
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const activePolls = backgroundJobService.getActivePollingCount();
      if (activePolls > 1) {
        console.log(`Warning: ${activePolls} active polling intervals detected. Cleaning up stale polls.`);
        // If we have more than 1 active poll but no current job, clean up
        if (!currentJob || (currentJob.status !== 'running' && currentJob.status !== 'pending')) {
          backgroundJobService.cleanupStalePolling();
        }
      }
    }, 30000); // Check every 30 seconds

    return () => clearInterval(cleanupInterval);
  }, [currentJob]);

  const loadJobHistory = async () => {
    try {
      const jobs = await backgroundJobService.getUserJobs();
      
      // Ensure jobs is an array
      if (!Array.isArray(jobs)) {
        console.error('Expected array but got:', typeof jobs, jobs);
        setJobHistory([]);
        return;
      }
      
      setJobHistory(jobs);
      
      // Check if there's a running job
      const runningJob = jobs.find(job => job.status === 'running' || job.status === 'pending');
      if (runningJob && runningJob._id) {
        console.log('Found running job:', runningJob._id);
        setCurrentJob(runningJob);
        startJobPolling(runningJob._id);
      } else {
        console.log('No running jobs found');
        // Clear any stale current job if no running jobs exist
        if (currentJob && (currentJob.status === 'running' || currentJob.status === 'pending')) {
          console.log('Clearing stale current job');
          setCurrentJob(null);
          backgroundJobService.stopAllPolling();
        }
      }
    } catch (error) {
      console.error('Error loading job history:', error);
      setJobHistory([]); // Set empty array on error
    }
  };

  // Function to handle cleanup of stale jobs
  const handleStaleJobCleanup = (jobId: string) => {
    console.log('Cleaning up stale job:', jobId);
    
    // Stop polling for this specific job
    backgroundJobService.stopPolling(jobId);
    
    // If this was the current job, clear it
    if (currentJob && currentJob._id === jobId) {
      setCurrentJob(null);
    }
    
    // Refresh job history to get updated status
    setTimeout(() => {
      loadJobHistory();
    }, 1000);
  };

  const startJobPolling = (jobId: string) => {
    // Validate job ID before starting polling
    if (!jobId || jobId === 'undefined' || jobId === 'null' || jobId.trim() === '') {
      console.error('Cannot start polling with invalid job ID:', jobId);
      return;
    }

    console.log('Starting job polling for:', jobId);
    
    backgroundJobService.startPolling(
      jobId,
      (update: JobStatusUpdate) => {
        setCurrentJob(update.job);
      },
      (completedJob: BackgroundJob) => {
        // Job completed successfully
        setCurrentJob(completedJob);
        
        // Clear prerequisite cache since analysis was successful
        prerequisiteService.clearCache();
        
        // Refresh ad analyses
        fetchAdAnalyses();
        
        toast({
          title: "Success",
          description: "Ad analysis completed successfully!"
        });
        
        // Auto-hide job progress after 5 seconds
        setTimeout(() => {
          setCurrentJob(null);
        }, 5000);
      },
      (errorMessage: string) => {
        // Job failed or was cancelled
        console.error('Job polling error:', errorMessage);
        
        // Handle job not found errors differently
        if (errorMessage.includes('Job not found') || errorMessage.includes('Invalid job ID')) {
          console.log('Job not found, cleaning up stale job state');
          handleStaleJobCleanup(jobId);
          
          toast({
            variant: "destructive",
            title: "Job Not Found",
            description: "The job is no longer available. It may have been cleaned up or expired."
          });
          
          return; // Don't show generic error toast
        }
        
        toast({
          variant: "destructive",
          title: "Analysis Failed",
          description: errorMessage
        });
        
        // Keep job visible for user to see error for actual failures
      }
    );
  };

  const toggleDataCollection = async () => {
    try {
      console.log('Toggling data collection. Current status:', isCollecting);
      const response = await axios.post('/api/v1/ad-analysis/toggle-collection', 
        {},  // No request body needed
        { headers: { Authorization: `Bearer ${token}` } }
      );
      console.log('Toggle response:', response.data);
      
      // Updated to use the correct response format
      if (response.data.status !== undefined) {
        setIsCollecting(response.data.status);
      } else {
        setIsCollecting(!isCollecting);  // Fallback
      }
      
      toast({
        title: response.data.status ? "Data Collection Started" : "Data Collection Stopped",
        description: response.data.status 
          ? "Your ad data will now be collected automatically."
          : "Ad data collection has been stopped.",
        variant: "default",
      });
    } catch (error) {
      console.error('Error toggling data collection:', error);
      toast({
        title: "Error",
        description: "Failed to update data collection status.",
        variant: "destructive",
      });
    }
  };

  const fetchAdAnalyses = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/v1/ad-analysis/', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      
      console.log('Ad analyses response:', response.data);
      
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
    setError(null);
    try {
      // Start background job
      const jobResponse = await backgroundJobService.startAdAnalysis();
      
      // Validate job response
      if (!jobResponse.job_id || jobResponse.job_id === 'undefined') {
        throw new Error('Invalid job ID received from server');
      }
  
      console.log('Analysis job started with ID:', jobResponse.job_id);
      
      setCurrentJob({
        _id: jobResponse.job_id,  // Map job_id to _id for consistency
        user_id: '',
        job_type: 'ad_analysis',
        status: 'pending',
        progress: 0,
        message: jobResponse.message,
        created_at: new Date().toISOString()
      });
      
      // Start polling for updates
      startJobPolling(jobResponse.job_id);
      
      // Refresh job history
      loadJobHistory();
      
      toast({
        title: "Analysis Started",
        description: "Your ad analysis is running in the background. You can continue using the app."
      });
      
    } catch (error: any) {
      console.error('Error starting ad analysis:', error);
      
      let errorMessage = "Failed to start ad analysis. Please try again later.";
      if (error.response?.status === 401) {
        errorMessage = "Authentication failed. Please log in again.";
      } else if (error.response?.status === 409) {
        errorMessage = "An analysis is already running. Please wait for it to complete.";
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      setError(errorMessage);
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage
      });
    }
  };

  const cancelCurrentJob = async () => {
    if (!currentJob) return;
    
    try {
      const success = await backgroundJobService.cancelJob(currentJob._id);
      if (success) {
        backgroundJobService.stopPolling(currentJob._id);
        setCurrentJob(null);
        toast({
          title: "Analysis Cancelled",
          description: "The ad analysis has been cancelled."
        });
      }
    } catch (error) {
      console.error('Error cancelling job:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to cancel the analysis."
      });
    }
  };

  const closeJobProgress = () => {
    setCurrentJob(null);
  };

  const deleteAdAnalysis = async (analysisId: string, adTitle: string) => {
    try {
      await axios.delete(`/api/v1/ad-analysis/${analysisId}`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      // Remove the deleted analysis from the local state
      setAdAnalyses(prevAnalyses => 
        prevAnalyses.filter(analysis => analysis._id !== analysisId)
      );

      toast({
        title: "Success",
        description: `"${adTitle || 'Ad'}" has been deleted successfully.`
      });
      
    } catch (error: any) {
      console.error('Error deleting ad analysis:', error);
      
      let errorMessage = "Failed to delete ad analysis";
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

  const handleDeleteClick = (analysisId: string, adTitle: string) => {
    if (window.confirm(`Are you sure you want to delete "${adTitle || 'this ad'}"? This action cannot be undone.`)) {
      deleteAdAnalysis(analysisId, adTitle);
    }
  };

  const deleteAllAdAnalyses = async () => {
    setDeletingAll(true);
    try {
      const response = await axios.delete('/api/v1/ad-analysis/all', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      // Clear the local state
      setAdAnalyses([]);

      toast({
        title: "Success",
        description: `${response.data.deleted_count || 'All'} ad analyses have been deleted successfully.`
      });
      
    } catch (error: any) {
      console.error('Error deleting all ad analyses:', error);
      
      let errorMessage = "Failed to delete all ad analyses";
      if (error.response?.status === 401) {
        errorMessage = "Authentication failed. Please log in again.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }
      
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage
      });
    } finally {
      setDeletingAll(false);
    }
  };

  const handleDeleteAllClick = () => {
    if (adAnalyses.length === 0) {
      toast({
        title: "No Data",
        description: "There are no ad analyses to delete."
      });
      return;
    }

    const confirmed = window.confirm(
      `Are you sure you want to delete ALL ${adAnalyses.length} ad analyses? This action cannot be undone and will permanently remove all your ad analysis data.`
    );
    
    if (confirmed) {
      const doubleConfirmed = window.confirm(
        "This is your final warning. Are you absolutely sure you want to delete ALL ad analyses? This action is irreversible."
      );
      
      if (doubleConfirmed) {
        deleteAllAdAnalyses();
      }
    }
  };

  const startEditing = (analysisId: string, field: 'product' | 'product_type', currentValue: string) => {
    setEditingFields(prev => ({
      ...prev,
      [analysisId]: {
        ...prev[analysisId],
        [field]: true
      }
    }));
    setEditValues(prev => ({
      ...prev,
      [analysisId]: {
        ...prev[analysisId],
        [field]: currentValue || ''
      }
    }));
  };

  const cancelEditing = (analysisId: string, field: 'product' | 'product_type') => {
    setEditingFields(prev => ({
      ...prev,
      [analysisId]: {
        ...prev[analysisId],
        [field]: false
      }
    }));
    setEditValues(prev => ({
      ...prev,
      [analysisId]: {
        ...prev[analysisId],
        [field]: undefined
      }
    }));
  };

  const updateAdAnalysis = async (analysisId: string, field: 'product' | 'product_type', newValue: string) => {
    try {
      const updateData = {
        [field]: newValue.trim()
      };

      const response = await axios.patch(`/api/v1/ad-analysis/${analysisId}`, updateData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.data.success && response.data.updated_analysis) {
        // Update the local state with the updated analysis
        setAdAnalyses(prevAnalyses => 
          prevAnalyses.map(analysis => 
            analysis._id === analysisId 
              ? { ...analysis, ad_analysis: { ...analysis.ad_analysis, [field]: newValue.trim() }}
              : analysis
          )
        );

        // Clear editing state
        cancelEditing(analysisId, field);

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

  const handleSaveEdit = (analysisId: string, field: 'product' | 'product_type') => {
    const newValue = editValues[analysisId]?.[field] || '';
    updateAdAnalysis(analysisId, field, newValue);
  };

  // Helper component for editable fields
  const EditableField = ({ 
    analysisId, 
    field, 
    value, 
    label 
  }: { 
    analysisId: string; 
    field: 'product' | 'product_type'; 
    value: string; 
    label: string; 
  }) => {
    const isEditing = editingFields[analysisId]?.[field] || false;
    const editValue = editValues[analysisId]?.[field] || '';

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
                onClick={() => handleSaveEdit(analysisId, field)}
                title="Save changes"
              >
                <Check className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-gray-600 hover:text-gray-700 hover:bg-gray-50"
                onClick={() => cancelEditing(analysisId, field)}
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
              [analysisId]: {
                ...prev[analysisId],
                [field]: e.target.value
              }
            }))}
            className="h-8 text-sm"
            placeholder={`Enter ${label.toLowerCase()}`}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSaveEdit(analysisId, field);
              } else if (e.key === 'Escape') {
                cancelEditing(analysisId, field);
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
            onClick={() => startEditing(analysisId, field, value)}
            title={`Edit ${label.toLowerCase()}`}
          >
            <Edit3 className="h-3 w-3" />
          </Button>
        </div>
        <p className="cursor-pointer" onClick={() => startEditing(analysisId, field, value)}>
          {value || 'N/A'}
        </p>
      </div>
    );
  };

  const isJobRunning = currentJob && (currentJob.status === 'running' || currentJob.status === 'pending');

  return (
    <div className="flex flex-col h-screen">
      <div className="bg-background py-4 px-8 border-b shadow-sm">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-3xl font-bold">Ad Analysis</h1>
          <div className="flex gap-3">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="data-collection"
                  checked={isCollecting}
                  onCheckedChange={toggleDataCollection}
                />
                <Label htmlFor="data-collection">
                  {isCollecting ? "Stop Data Collection" : "Start Data Collection"}
                </Label>
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowJobHistory(!showJobHistory)}
                className="flex items-center space-x-2"
              >
                <History className="h-4 w-4" />
                <span>History</span>
              </Button>
              
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteAllClick}
                disabled={deletingAll || isJobRunning}
                className="flex items-center space-x-2"
              >
                {deletingAll ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <AlertTriangle className="h-4 w-4" />
                )}
                <span>{deletingAll ? "Deleting..." : "Delete All"}</span>
              </Button>
              
              <Button 
                onClick={analyzeAds}
                disabled={isJobRunning}
                className="flex items-center space-x-2"
              >
                <Play className="h-4 w-4" />
                <span>{isJobRunning ? "Analysis Running..." : "Start Analysis"}</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto py-6 px-8">
        <div className="container mx-auto space-y-6">
          {/* Current Job Progress */}
          {currentJob && (
            <JobProgress 
              job={currentJob} 
              onCancel={isJobRunning ? cancelCurrentJob : undefined}
              onClose={!isJobRunning ? closeJobProgress : undefined}
              showCloseButton={!isJobRunning}
            />
          )}

          {/* Job History */}
          {showJobHistory && jobHistory && jobHistory.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recent Jobs</CardTitle>
                <CardDescription>Your analysis job history</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {jobHistory.slice(0, 5).map((job) => (
                    <div key={job._id} className="flex items-center justify-between p-3 border rounded-md">
                      <div className="flex items-center space-x-3">
                        <div className={`w-3 h-3 rounded-full ${
                          job.status === 'completed' ? 'bg-green-500' :
                          job.status === 'failed' ? 'bg-red-500' :
                          job.status === 'cancelled' ? 'bg-gray-500' :
                          'bg-blue-500'
                        }`} />
                        <div>
                          <p className="text-sm font-medium">{job.status.toUpperCase()}</p>
                          <p className="text-xs text-gray-500">
                            {new Date(job.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                      <div className="text-sm text-gray-600">
                        {job.progress}%
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Ad Analyses Results */}
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : error ? (
            <div className="flex flex-col justify-center items-center h-64 text-center">
              <p className="text-lg text-destructive mb-4">Error: {error}</p>
              <Button onClick={fetchAdAnalyses} variant="outline">Try Again</Button>
            </div>
          ) : adAnalyses.length === 0 ? (
            <div className="flex flex-col justify-center items-center h-64 text-center">
              <p className="text-lg text-muted-foreground mb-4">No ad analyses found.</p>
              <p className="text-muted-foreground mb-6">Click the "Start Analysis" button to analyze your Facebook ads.</p>
              <Button onClick={analyzeAds} disabled={isJobRunning}>
                <Play className="h-4 w-4 mr-2" />
                {isJobRunning ? "Analysis Running..." : "Start Analysis"}
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {adAnalyses.map((analysis) => (
                <Card key={analysis._id} className="overflow-hidden">
                  <CardHeader className="relative">
                    <div className="flex items-start justify-between">
                      <CardTitle className="pr-20">
                        <Link 
                          to={`/ad-detail/${analysis.ad_id || analysis._id}`} 
                          className="hover:text-blue-600 hover:underline transition-colors"
                        >
                          {analysis.ad_title || 'Untitled Ad'}
                        </Link>
                      </CardTitle>
                      <div className="absolute top-4 right-6 flex flex-col items-end space-y-2">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          analysis.ad_status === 'ACTIVE' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {analysis.ad_status || 'Unknown'}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={(e) => {
                            e.preventDefault();
                            handleDeleteClick(analysis._id, analysis.ad_title || 'Untitled Ad');
                          }}
                          title="Delete this ad analysis"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
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
                        <div className="grid grid-cols-3 gap-3 text-sm">
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Hook</p>
                            <p>{analysis.ad_analysis?.hook || 'N/A'}</p>
                          </div>
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Tone</p>
                            <p>{analysis.ad_analysis?.tone || 'N/A'}</p>
                          </div>
                          <EditableField
                            analysisId={analysis._id}
                            field="product"
                            value={analysis.ad_analysis?.product || ''}
                            label="Product"
                          />
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Power Phrases</p>
                            <p>{analysis.ad_analysis?.power_phrases || 'N/A'}</p>
                          </div>
                          <div>
                            <p className="font-bold text-gray-800 mb-1">Visual</p>
                            <p>{analysis.ad_analysis?.visual || 'N/A'}</p>
                          </div>
                          <EditableField
                            analysisId={analysis._id}
                            field="product_type"
                            value={analysis.ad_analysis?.product_type || ''}
                            label="Product Type"
                          />
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