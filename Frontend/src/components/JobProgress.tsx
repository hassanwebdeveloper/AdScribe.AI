import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { X, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { BackgroundJob } from '@/services/backgroundJobService';

interface JobProgressProps {
  job: BackgroundJob | null;
  onCancel?: () => void;
  onClose?: () => void;
  showCloseButton?: boolean;
}

const JobProgress: React.FC<JobProgressProps> = ({ 
  job, 
  onCancel, 
  onClose, 
  showCloseButton = false 
}) => {
  if (!job) return null;

  const getStatusIcon = () => {
    switch (job.status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'cancelled':
        return <AlertCircle className="h-5 w-5 text-gray-500" />;
      case 'running':
      case 'pending':
      default:
        return <Clock className="h-5 w-5 text-blue-500" />;
    }
  };

  const getStatusColor = () => {
    switch (job.status) {
      case 'completed':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'failed':
        return 'text-red-700 bg-red-50 border-red-200';
      case 'cancelled':
        return 'text-gray-700 bg-gray-50 border-gray-200';
      case 'running':
      case 'pending':
      default:
        return 'text-blue-700 bg-blue-50 border-blue-200';
    }
  };

  const getProgressColor = () => {
    switch (job.status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'cancelled':
        return 'bg-gray-500';
      case 'running':
        return job.progress > 50 ? 'bg-blue-500' : 'bg-yellow-500';
      default:
        return 'bg-gray-400';
    }
  };

  const isRunning = job.status === 'running' || job.status === 'pending';
  const isComplete = job.status === 'completed';
  const isFailed = job.status === 'failed';
  const isCancelled = job.status === 'cancelled';

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${remainingSeconds}s`;
  };

  const getProgressMessage = (progress: number) => {
    if (progress <= 5) return 'Starting analysis...';
    if (progress <= 10) return 'Checking previously analyzed videos...';
    if (progress <= 20) return 'Fetching Facebook ads...';
    if (progress <= 40) return 'Processing ad data...';
    if (progress <= 50) return 'Getting video URLs...';
    if (progress <= 75) return 'Downloading videos...';
    if (progress <= 80) return 'Transcribing videos...';
    if (progress <= 85) return 'Analyzing content with AI...';
    if (progress <= 90) return 'Finalizing results...';
    if (progress < 100) return 'Almost done...';
    return 'Completed!';
  };

  return (
    <Card className={`w-full border-2 ${getStatusColor()}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {getStatusIcon()}
            <CardTitle className="text-lg">
              {isComplete && 'Analysis Complete'}
              {isFailed && 'Analysis Failed'}
              {isCancelled && 'Analysis Cancelled'}
              {isRunning && 'Analyzing Ads'}
            </CardTitle>
          </div>
          
          <div className="flex items-center space-x-2">
            {isRunning && onCancel && (
              <Button
                variant="outline"
                size="sm"
                onClick={onCancel}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                Cancel
              </Button>
            )}
            {showCloseButton && onClose && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
        
        <CardDescription className="text-sm">
          {isComplete && `Analysis completed successfully${job.duration ? ` in ${formatDuration(job.duration)}` : ''}`}
          {isFailed && (job.error_message || 'An error occurred during analysis')}
          {isCancelled && 'Analysis was cancelled by user'}
          {isRunning && getProgressMessage(job.progress)}
        </CardDescription>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="space-y-3">
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="font-medium">Progress</span>
              <span>{job.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all duration-300 ${getProgressColor()}`}
                style={{ width: `${Math.min(job.progress, 100)}%` }}
              />
            </div>
          </div>

          {/* Job Details */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-600">Job ID:</span>
              <span className="text-xs text-gray-500 ml-2">
                ID: {job._id.slice(0, 8)}...
              </span>
            </div>
            <div>
              <span className="font-medium text-gray-600">Started:</span>
              <p className="text-gray-900">
                {new Date(job.created_at).toLocaleTimeString()}
              </p>
            </div>
          </div>

          {/* Additional Message */}
          {job.message && job.message !== getProgressMessage(job.progress) && (
            <div className="mt-3 p-3 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-700">{job.message}</p>
            </div>
          )}

          {/* Result Summary for Completed Jobs */}
          {isComplete && job.result && (
            <div className="mt-3 p-3 bg-green-50 rounded-md">
              <p className="text-sm text-green-800">
                <span className="font-medium">Result:</span> {job.result.summary || 'Analysis completed successfully'}
              </p>
              {job.result.ads_analyzed && (
                <p className="text-xs text-green-600 mt-1">
                  {job.result.ads_analyzed} ads were analyzed
                </p>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default JobProgress; 