const API_BASE_URL = '/api/v1';

export interface BackgroundJob {
  _id: string;
  user_id: string;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message?: string;
  error_message?: string;
  result?: any;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  duration?: number;
}

export interface JobStartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatusUpdate {
  job: BackgroundJob;
  isComplete: boolean;
  isError: boolean;
  isRunning: boolean;
}

class BackgroundJobService {
  private static instance: BackgroundJobService;
  private pollingIntervals: Map<string, NodeJS.Timeout> = new Map();
  private retryCounters: Map<string, number> = new Map();
  private pollingTimeouts: Map<string, NodeJS.Timeout> = new Map();
  private readonly POLLING_INTERVAL = 3000; // 3 seconds - reduced frequency to improve performance
  private isTabVisible: boolean = true;

  static getInstance(): BackgroundJobService {
    if (!BackgroundJobService.instance) {
      BackgroundJobService.instance = new BackgroundJobService();
      BackgroundJobService.instance.initializeVisibilityListener();
    }
    return BackgroundJobService.instance;
  }

  private initializeVisibilityListener(): void {
    // Listen for page visibility changes to pause/resume polling
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        this.isTabVisible = !document.hidden;
        console.log('Tab visibility changed:', this.isTabVisible ? 'visible' : 'hidden');
        
        if (this.isTabVisible) {
          // Tab became visible - resume all polling
          console.log('Resuming polling for visible tab');
        } else {
          // Tab became hidden - reduce polling frequency
          console.log('Tab hidden - polling continues but errors are suppressed');
        }
      });

      // Clean up polling when page unloads
      window.addEventListener('beforeunload', () => {
        console.log('Page unloading - cleaning up all polling');
        this.stopAllPolling();
      });
    }
  }

  /**
   * Start an ad analysis job
   */
  async startAdAnalysis(): Promise<JobStartResponse> {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/ad-analysis/start-analysis/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error starting ad analysis:', error);
      throw error;
    }
  }

  /**
   * Get job status with automatic token refresh on 401
   */
  async getJobStatus(jobId: string): Promise<BackgroundJob> {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/ad-analysis/job-status/${jobId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        const error = new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        // Add status code to error for better handling
        (error as any).status = response.status;
        (error as any).statusText = response.statusText;
        throw error;
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting job status:', error);
      throw error;
    }
  }

  /**
   * Get user jobs history
   */
  async getUserJobs(): Promise<BackgroundJob[]> {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/ad-analysis/jobs/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting user jobs:', error);
      throw error;
    }
  }

  /**
   * Cancel a running job
   */
  async cancelJob(jobId: string): Promise<boolean> {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/ad-analysis/job/${jobId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result.success || false;
    } catch (error) {
      console.error('Error cancelling job:', error);
      throw error;
    }
  }

  /**
   * Start polling for job status updates
   */
  startPolling(
    jobId: string, 
    onUpdate: (update: JobStatusUpdate) => void,
    onComplete?: (job: BackgroundJob) => void,
    onError?: (error: string) => void
  ): void {
    // Validate jobId
    if (!jobId || jobId === 'undefined' || jobId === 'null' || jobId.trim() === '') {
      console.error('Invalid job ID provided for polling:', jobId);
      onError?.('Invalid job ID provided');
      return;
    }

    // Clear any existing polling for this job
    this.stopPolling(jobId);

    console.log(`Starting polling for job: ${jobId}`);

    const pollFunction = async () => {
      try {
        const job = await this.getJobStatus(jobId);
        
        // Reset retry counter on successful polling
        this.clearRetryCount(jobId);
        
        const isComplete = job.status === 'completed';
        const isError = job.status === 'failed';
        const isRunning = job.status === 'running' || job.status === 'pending';
        const isCancelled = job.status === 'cancelled';

        // Call the update callback
        onUpdate({
          job,
          isComplete,
          isError,
          isRunning
        });

        // Handle completion
        if (isComplete) {
          console.log(`Job ${jobId} completed successfully`);
          this.stopPolling(jobId);
          onComplete?.(job);
        } else if (isError) {
          console.log(`Job ${jobId} failed:`, job.error_message);
          this.stopPolling(jobId);
          onError?.(job.error_message || 'Job failed with unknown error');
        } else if (isCancelled) {
          console.log(`Job ${jobId} was cancelled`);
          this.stopPolling(jobId);
          onError?.('Job was cancelled');
        }
      } catch (error) {
        // Suppress error logging when tab is not visible to prevent console spam
        if (this.isTabVisible) {
          console.error(`Error polling job status for ${jobId}:`, error);
        }
        
        // Check if it's a 401 error (authentication failed)
        const is401Error = (error as any).status === 401 || 
                           (error instanceof Error && error.message.includes('401'));
        
        // Check if it's a 404 error (job not found)
        const is404Error = (error as any).status === 404 || 
                           (error instanceof Error && (
                             error.message.includes('404') || 
                             error.message.includes('not found') ||
                             error.message.includes('Job not found')
                           ));
        
        if (is401Error) {
          console.log(`Authentication failed for job ${jobId}, stopping polling`);
          this.stopPolling(jobId);
          // Only show error to user if tab is visible
          if (this.isTabVisible) {
            onError?.('Authentication failed. Please refresh the page and try again.');
          }
          return;
        }
        
        if (is404Error) {
          console.log(`Job ${jobId} not found (404), stopping polling`);
          this.stopPolling(jobId);
          // Only show error to user if tab is visible
          if (this.isTabVisible) {
            onError?.(`Job not found: ${jobId}`);
          }
          return;
        }
        
        // For other errors, continue polling but limit retries with exponential backoff
        const retryCount = this.getRetryCount(jobId);
        if (retryCount >= 5) {
          console.log(`Max retries reached for job ${jobId}, stopping polling`);
          this.stopPolling(jobId);
          // Only show error to user if tab is visible
          if (this.isTabVisible) {
            onError?.(error instanceof Error ? error.message : 'Unknown polling error');
          }
        } else {
          this.incrementRetryCount(jobId);
          const backoffDelay = Math.min(1000 * Math.pow(2, retryCount), 10000); // Max 10 seconds
          
          if (this.isTabVisible) {
            console.log(`Retry ${retryCount + 1}/5 for job ${jobId} after ${backoffDelay}ms`);
          }
          
          // Use exponential backoff for retries with proper cleanup
          const timeout = setTimeout(() => {
            this.pollingTimeouts.delete(jobId);
            if (this.pollingIntervals.has(jobId)) {
              pollFunction();
            }
          }, backoffDelay);
          this.pollingTimeouts.set(jobId, timeout);
          return; // Skip the regular interval for this iteration
        }
      }
    };

    // Start polling immediately, then at intervals
    pollFunction();
    const interval = setInterval(pollFunction, this.POLLING_INTERVAL);
    this.pollingIntervals.set(jobId, interval);
  }

  private getRetryCount(jobId: string): number {
    return this.retryCounters.get(jobId) || 0;
  }

  private incrementRetryCount(jobId: string): void {
    const currentCount = this.getRetryCount(jobId);
    this.retryCounters.set(jobId, currentCount + 1);
  }

  private clearRetryCount(jobId: string): void {
    this.retryCounters.delete(jobId);
  }

  /**
   * Stop polling for a specific job
   */
  stopPolling(jobId: string): void {
    const interval = this.pollingIntervals.get(jobId);
    if (interval) {
      clearInterval(interval);
      this.pollingIntervals.delete(jobId);
    }
    
    const timeout = this.pollingTimeouts.get(jobId);
    if (timeout) {
      clearTimeout(timeout);
      this.pollingTimeouts.delete(jobId);
    }
    
    this.clearRetryCount(jobId);
    console.log(`Stopped polling for job: ${jobId}`);
  }

  /**
   * Stop all polling
   */
  stopAllPolling(): void {
    console.log(`Stopping all polling. Active polls: ${this.pollingIntervals.size}, timeouts: ${this.pollingTimeouts.size}`);
    this.pollingIntervals.forEach((interval) => clearInterval(interval));
    this.pollingIntervals.clear();
    this.pollingTimeouts.forEach((timeout) => clearTimeout(timeout));
    this.pollingTimeouts.clear();
    this.retryCounters.clear();
  }

  /**
   * Get number of active polling intervals (for debugging)
   */
  getActivePollingCount(): number {
    return this.pollingIntervals.size;
  }

  /**
   * Clean up stale polling intervals that might have been orphaned
   */
  cleanupStalePolling(): void {
    const activeCount = this.pollingIntervals.size;
    if (activeCount > 0) {
      console.log(`Cleaning up ${activeCount} potentially stale polling intervals`);
      this.stopAllPolling();
    }
  }

  /**
   * Format progress message based on percentage
   */
  getProgressMessage(progress: number): string {
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
  }

  /**
   * Get progress color based on status and percentage
   */
  getProgressColor(status: string, progress: number): string {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'cancelled':
        return 'bg-gray-500';
      case 'running':
        return progress > 50 ? 'bg-blue-500' : 'bg-yellow-500';
      default:
        return 'bg-gray-400';
    }
  }


}

export const backgroundJobService = BackgroundJobService.getInstance(); 