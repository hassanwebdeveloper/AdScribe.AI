# Background Jobs Implementation

This document explains the implementation of background jobs for ad analysis to prevent UI blocking and improve user experience.

## Overview

The background job system allows users to:
1. **Start ad analysis** and get immediate response without waiting
2. **Track progress** of analysis in real-time
3. **Cancel running jobs** if needed
4. **View job history** to monitor past analyses
5. **Get notified** when analysis is complete

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Endpoints │    │   Background    │
│   React App     │───▶│   FastAPI       │───▶│   Job Service   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Job Status    │    │   Job Status    │    │   AsyncIO Task  │
│   Polling       │◀───│   Endpoints     │◀───│   Management    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │   AI Agent      │
                                              │   Execution     │
                                              └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │   Database      │
                                              │   Storage       │
                                              └─────────────────┘
```

## Database Schema

### Background Jobs Collection

**Model:** `app.models.job_status.BackgroundJob`

```python
{
    "_id": "ObjectId",           # Job ID
    "user_id": "string",         # User who started the job
    "job_type": "ad_analysis",   # Type of job
    "status": "pending|running|completed|failed|cancelled",
    "progress": 85,              # Progress percentage (0-100)
    "message": "Processing videos...",  # Current status message
    "error_message": null,       # Error details if failed
    
    # Job parameters
    "parameters": {
        "access_token": "fb_1234...",  # Partial token for debugging
        "account_id": "act_123456"     # Facebook ad account ID
    },
    
    # Results
    "result_count": 5,           # Number of analyses completed
    "results": [...],            # Optional: store results if needed
    
    # Timestamps
    "created_at": "2024-01-01T10:00:00Z",
    "started_at": "2024-01-01T10:00:05Z",
    "completed_at": "2024-01-01T10:05:30Z",
    
    # Duration tracking
    "estimated_duration_seconds": 300,  # Initial estimate
    "actual_duration_seconds": 325      # Actual time taken
}
```

## API Endpoints

### 1. Start Analysis (Non-blocking)

**Endpoint:** `POST /api/v1/ad_analysis/start-analysis/`

**Response:** `202 Accepted`
```json
{
    "job_id": "65f8b2c4d1e2f3a4b5c6d7e8",
    "status": "pending",
    "message": "Ad analysis job started successfully. Use the job ID to track progress.",
    "estimated_duration_seconds": 300
}
```

**Frontend Usage:**
```typescript
// Start analysis
const response = await fetch('/api/v1/ad_analysis/start-analysis/', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
});

if (response.status === 202) {
    const { job_id } = await response.json();
    // Start polling for status
    pollJobStatus(job_id);
} else if (response.status === 409) {
    // Job already running
    alert("Analysis already in progress!");
}
```

### 2. Get Job Status

**Endpoint:** `GET /api/v1/ad_analysis/job-status/{job_id}`

**Response:** `200 OK`
```json
{
    "_id": "65f8b2c4d1e2f3a4b5c6d7e8",
    "user_id": "user_123",
    "job_type": "ad_analysis",
    "status": "running",
    "progress": 65,
    "message": "Analyzing video transcriptions...",
    "error_message": null,
    "result_count": null,
    "created_at": "2024-01-01T10:00:00Z",
    "started_at": "2024-01-01T10:00:05Z",
    "completed_at": null,
    "estimated_duration_seconds": 300,
    "actual_duration_seconds": null
}
```

**Frontend Usage:**
```typescript
// Poll job status
const pollJobStatus = async (jobId: string) => {
    const response = await fetch(`/api/v1/ad_analysis/job-status/${jobId}`);
    const job = await response.json();
    
    // Update UI with progress
    updateProgressBar(job.progress);
    updateStatusMessage(job.message);
    
    if (job.status === 'completed') {
        // Analysis complete - refresh data
        refreshAdAnalyses();
    } else if (job.status === 'failed') {
        // Show error
        showError(job.error_message);
    } else {
        // Continue polling
        setTimeout(() => pollJobStatus(jobId), 2000);
    }
};
```

### 3. Get User Jobs

**Endpoint:** `GET /api/v1/ad_analysis/jobs/`

**Response:** Array of recent jobs
```json
[
    {
        "_id": "65f8b2c4d1e2f3a4b5c6d7e8",
        "status": "completed",
        "progress": 100,
        "message": "Analysis completed successfully! Processed 8 ads.",
        "result_count": 8,
        "created_at": "2024-01-01T10:00:00Z",
        "actual_duration_seconds": 325
    },
    {
        "_id": "65f8b2c4d1e2f3a4b5c6d7e9",
        "status": "failed",
        "progress": 45,
        "error_message": "Facebook API rate limit exceeded",
        "created_at": "2024-01-01T09:30:00Z"
    }
]
```

### 4. Cancel Job

**Endpoint:** `DELETE /api/v1/ad_analysis/job/{job_id}`

**Response:** `200 OK`
```json
{
    "message": "Job cancelled successfully"
}
```

### 5. Legacy Endpoint (Deprecated)

**Endpoint:** `POST /api/v1/ad_analysis/analyze/` (deprecated)

Still available for backward compatibility but marked as deprecated.

## Background Job Service

### Key Features

#### 1. Job Management
```python
class BackgroundJobService:
    async def start_ad_analysis_job(self, user_id: str, access_token: str, account_id: str) -> str:
        """Start analysis job and return job ID immediately"""
        
    async def get_job_status(self, job_id: str, user_id: str) -> Optional[BackgroundJobResponse]:
        """Get current job status with security check"""
        
    async def cancel_job(self, job_id: str, user_id: str) -> bool:
        """Cancel running job gracefully"""
```

#### 2. Progress Tracking
```python
# Progress stages during execution:
# 5%   - Job started
# 10%  - Checking previously analyzed videos
# 20%  - Fetching Facebook ads
# 35%  - Getting video URLs
# 50%  - Downloading videos
# 65%  - Transcribing videos
# 80%  - Analyzing content
# 90%  - Finalizing results
# 100% - Completed
```

#### 3. Error Handling
```python
# Job statuses:
# PENDING   - Job created, waiting to start
# RUNNING   - Job is currently executing
# COMPLETED - Job finished successfully
# FAILED    - Job encountered an error
# CANCELLED - Job was cancelled by user
```

#### 4. Security & Isolation
- ✅ **User-specific jobs** - Users can only see/manage their own jobs
- ✅ **Secure cancellation** - Only job owner can cancel
- ✅ **Parameter sanitization** - Sensitive data (tokens) partially masked
- ✅ **Resource cleanup** - Completed tasks removed from memory

## Frontend Integration

### React Component Example

```typescript
import React, { useState, useEffect } from 'react';

interface JobStatus {
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress: number;
    message: string;
    error_message?: string;
}

const AdAnalysisPage: React.FC = () => {
    const [currentJob, setCurrentJob] = useState<JobStatus | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    const startAnalysis = async () => {
        try {
            const response = await fetch('/api/v1/ad_analysis/start-analysis/', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${getToken()}` }
            });

            if (response.status === 202) {
                const job = await response.json();
                setCurrentJob(job);
                setIsAnalyzing(true);
                pollJobStatus(job.job_id);
            } else if (response.status === 409) {
                alert('Analysis already in progress!');
            }
        } catch (error) {
            console.error('Error starting analysis:', error);
        }
    };

    const pollJobStatus = async (jobId: string) => {
        try {
            const response = await fetch(`/api/v1/ad_analysis/job-status/${jobId}`);
            const job = await response.json();

            setCurrentJob(job);

            if (job.status === 'completed') {
                setIsAnalyzing(false);
                // Refresh ad analyses list
                window.location.reload();
            } else if (job.status === 'failed') {
                setIsAnalyzing(false);
                alert(`Analysis failed: ${job.error_message}`);
            } else if (job.status !== 'cancelled') {
                // Continue polling
                setTimeout(() => pollJobStatus(jobId), 2000);
            }
        } catch (error) {
            console.error('Error polling job status:', error);
            setIsAnalyzing(false);
        }
    };

    const cancelAnalysis = async () => {
        if (!currentJob) return;

        try {
            await fetch(`/api/v1/ad_analysis/job/${currentJob.job_id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${getToken()}` }
            });
            setIsAnalyzing(false);
            setCurrentJob(null);
        } catch (error) {
            console.error('Error cancelling job:', error);
        }
    };

    return (
        <div>
            <h1>Ad Analysis</h1>
            
            {!isAnalyzing ? (
                <button onClick={startAnalysis} className="btn-primary">
                    Start Analysis
                </button>
            ) : (
                <div className="analysis-progress">
                    <div className="progress-bar">
                        <div 
                            className="progress-fill" 
                            style={{ width: `${currentJob?.progress || 0}%` }}
                        />
                    </div>
                    <p>{currentJob?.message}</p>
                    <button onClick={cancelAnalysis} className="btn-secondary">
                        Cancel
                    </button>
                </div>
            )}
        </div>
    );
};
```

### Progress Bar Component

```typescript
interface ProgressBarProps {
    progress: number;
    message: string;
    status: string;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ progress, message, status }) => {
    const getStatusColor = () => {
        switch (status) {
            case 'running': return '#3b82f6';
            case 'completed': return '#10b981';
            case 'failed': return '#ef4444';
            default: return '#6b7280';
        }
    };

    return (
        <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div 
                className="h-2.5 rounded-full transition-all duration-300"
                style={{ 
                    width: `${progress}%`,
                    backgroundColor: getStatusColor()
                }}
            />
            <p className="text-sm text-gray-600 mt-2">{message}</p>
        </div>
    );
};
```

## Benefits

### User Experience
- ⚡ **Immediate Response** - UI doesn't freeze during analysis
- 📊 **Real-time Progress** - Users see what's happening
- 🚫 **Cancellation** - Users can stop unwanted jobs
- 📱 **Multi-tab Support** - Job status syncs across tabs
- 🔄 **Resume Capability** - Users can leave and come back

### Performance
- 🏃 **Non-blocking** - UI remains responsive
- 📈 **Scalable** - Multiple users can run analyses simultaneously
- 💾 **Memory Efficient** - Jobs cleaned up after completion
- ⚡ **Fast Polling** - 2-second status updates

### Developer Experience
- 🛠️ **Easy Integration** - Simple API endpoints
- 📝 **Comprehensive Logging** - Detailed job tracking
- 🔒 **Secure** - User isolation and permission checks
- 🐛 **Debuggable** - Error tracking and job history

## Error Handling

### Common Error Scenarios

#### 1. Facebook API Issues
```json
{
    "status": "failed",
    "error_message": "Facebook API rate limit exceeded. Please try again in 1 hour.",
    "progress": 20
}
```

#### 2. OpenAI API Issues
```json
{
    "status": "failed", 
    "error_message": "OpenAI API quota exceeded. Please check your API limits.",
    "progress": 65
}
```

#### 3. Network Issues
```json
{
    "status": "failed",
    "error_message": "Network timeout while downloading videos. Please try again.",
    "progress": 45
}
```

#### 4. Invalid Configuration
```json
{
    "status": "failed",
    "error_message": "Invalid Facebook access token. Please update your credentials.",
    "progress": 10
}
```

### Error Recovery

1. **Automatic Retry** - Some transient errors trigger automatic retry
2. **Graceful Degradation** - Partial results saved when possible
3. **User Notification** - Clear error messages with actionable advice
4. **Job History** - Failed jobs remain visible for debugging

## Monitoring & Maintenance

### Job Cleanup
```python
# Automatic cleanup of old jobs
await background_job_service.cleanup_old_jobs(days_old=7)
```

### Health Monitoring
```python
# Monitor job success rates
successful_jobs = await db.background_jobs.count_documents({
    "status": "completed",
    "created_at": {"$gte": datetime.utcnow() - timedelta(days=1)}
})

failed_jobs = await db.background_jobs.count_documents({
    "status": "failed", 
    "created_at": {"$gte": datetime.utcnow() - timedelta(days=1)}
})

success_rate = successful_jobs / (successful_jobs + failed_jobs) * 100
```

### Performance Metrics
- **Average completion time** - Track job duration trends
- **Peak usage times** - Identify capacity needs
- **Error patterns** - Monitor common failure points
- **User engagement** - Track job creation vs completion rates

## Future Enhancements

### Advanced Features
- 📧 **Email Notifications** - Notify users when jobs complete
- 📱 **Push Notifications** - Real-time updates via WebSocket
- 🔄 **Job Queue Priority** - Premium users get faster processing
- 📊 **Batch Processing** - Analyze multiple accounts simultaneously

### Scaling Options
- 🔄 **Redis Task Queue** - Use Celery for distributed processing
- 🐳 **Containerization** - Scale with Docker containers
- ☁️ **Cloud Functions** - Serverless analysis processing
- 📈 **Load Balancing** - Distribute jobs across multiple workers

## Testing

### Unit Tests
```python
async def test_job_creation():
    service = BackgroundJobService()
    job_id = await service.start_ad_analysis_job("user_123", "token", "account")
    assert job_id is not None
    
    job = await service.get_job_status(job_id, "user_123")
    assert job.status == JobStatus.PENDING
```

### Integration Tests
```python
async def test_full_workflow():
    # Start job
    response = await client.post("/api/v1/ad_analysis/start-analysis/")
    assert response.status_code == 202
    
    job_id = response.json()["job_id"]
    
    # Poll until complete
    while True:
        status_response = await client.get(f"/api/v1/ad_analysis/job-status/{job_id}")
        job = status_response.json()
        
        if job["status"] in ["completed", "failed"]:
            break
            
        await asyncio.sleep(1)
    
    assert job["status"] == "completed"
```

## Migration Guide

### From Synchronous to Asynchronous

#### Before (Blocking)
```typescript
const analyzeAds = async () => {
    setLoading(true);
    try {
        const response = await fetch('/api/v1/ad_analysis/analyze/', {
            method: 'POST'
        });
        const results = await response.json();
        setAdAnalyses(results);
    } finally {
        setLoading(false);
    }
};
```

#### After (Non-blocking)
```typescript
const analyzeAds = async () => {
    try {
        const response = await fetch('/api/v1/ad_analysis/start-analysis/', {
            method: 'POST'
        });
        
        if (response.status === 202) {
            const { job_id } = await response.json();
            pollJobStatus(job_id);
        }
    } catch (error) {
        console.error('Error starting analysis:', error);
    }
};
```

The background job system provides a robust, scalable solution for long-running ad analysis tasks while maintaining excellent user experience. 