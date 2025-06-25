const API_BASE_URL = '/api/v1';

export interface PrerequisiteStatus {
  has_facebook_credentials: boolean;
  has_analyzed_ads: boolean;
  is_complete: boolean;
  missing_requirements: string[];
  message: string;
}

class PrerequisiteService {
  private static instance: PrerequisiteService;
  private cachedStatus: PrerequisiteStatus | null = null;
  private lastCheckTime: number = 0;
  private readonly CACHE_DURATION = 30000; // 30 seconds

  static getInstance(): PrerequisiteService {
    if (!PrerequisiteService.instance) {
      PrerequisiteService.instance = new PrerequisiteService();
    }
    return PrerequisiteService.instance;
  }

  /**
   * Check if user has completed all prerequisites
   */
  async checkPrerequisites(): Promise<PrerequisiteStatus> {
    // Return cached result if still valid
    const now = Date.now();
    if (this.cachedStatus && (now - this.lastCheckTime) < this.CACHE_DURATION) {
      return this.cachedStatus;
    }

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/prerequisites/check`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const status = await response.json();
      
      // Cache the result
      this.cachedStatus = status;
      this.lastCheckTime = now;
      
      return status;
    } catch (error) {
      console.error('Error checking prerequisites:', error);
      // Return a default failed state
      return {
        has_facebook_credentials: false,
        has_analyzed_ads: false,
        is_complete: false,
        missing_requirements: ['Unable to check prerequisites'],
        message: 'Unable to verify prerequisites. Please check your connection and try again.',
      };
    }
  }

  /**
   * Clear cached status (useful after user makes changes)
   */
  clearCache(): void {
    this.cachedStatus = null;
    this.lastCheckTime = 0;
  }

  /**
   * Quick check if user meets prerequisites (uses cache if available)
   */
  async isComplete(): Promise<boolean> {
    const status = await this.checkPrerequisites();
    return status.is_complete;
  }

  /**
   * Get missing requirements
   */
  async getMissingRequirements(): Promise<string[]> {
    const status = await this.checkPrerequisites();
    return status.missing_requirements;
  }

  /**
   * Get user-friendly message about prerequisites
   */
  async getMessage(): Promise<string> {
    const status = await this.checkPrerequisites();
    return status.message;
  }
}

export const prerequisiteService = PrerequisiteService.getInstance(); 