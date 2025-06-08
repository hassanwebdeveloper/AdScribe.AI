import React, { useEffect, useState, ReactNode } from 'react';
import { prerequisiteService, PrerequisiteStatus } from '../services/prerequisiteService';
import { AlertCircle, Settings, BarChart3, CheckCircle2, XCircle, ArrowRight, LogOut } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface PrerequisiteGuardProps {
  children: ReactNode;
  pageName: string; // Name of the page being protected (e.g., "Dashboard", "Chat")
}

const PrerequisiteGuard: React.FC<PrerequisiteGuardProps> = ({ children, pageName }) => {
  const [status, setStatus] = useState<PrerequisiteStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { logout } = useAuth();

  useEffect(() => {
    checkPrerequisites();
  }, []);

  const checkPrerequisites = async () => {
    setLoading(true);
    try {
      const prereqStatus = await prerequisiteService.checkPrerequisites();
      setStatus(prereqStatus);
    } catch (error) {
      console.error('Error checking prerequisites:', error);
    } finally {
      setLoading(false);
    }
  };

  const retry = () => {
    prerequisiteService.clearCache();
    checkPrerequisites();
  };

  const handlePrimaryAction = () => {
    if (!status?.has_facebook_credentials) {
      navigate('/settings');
    } else if (!status?.has_analyzed_ads) {
      navigate('/ad-analysis');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Checking prerequisites...</p>
        </div>
      </div>
    );
  }

  if (!status || !status.is_complete) {
    const nextAction = !status?.has_facebook_credentials ? 'Configure Settings' : 'Run Ad Analysis';
    const nextRoute = !status?.has_facebook_credentials ? '/settings' : '/ad-analysis';

    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
              <AlertCircle className="h-6 w-6 text-red-600" />
            </div>
            <h1 className="text-xl font-semibold text-gray-900 mb-2">
              Setup Required
            </h1>
            <p className="text-gray-600">
              Complete the setup process to access {pageName}
            </p>
          </div>

          {/* Status Message */}
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
            <p className="text-sm text-blue-800">{status?.message || 'Please complete the required setup steps.'}</p>
          </div>

          {/* Requirements Checklist */}
          <div className="space-y-3 mb-6">
            <h3 className="text-sm font-medium text-gray-900">Setup Progress:</h3>
            
            <div className="space-y-3">
              {/* Facebook Credentials */}
              <div className={`flex items-center space-x-3 p-3 rounded-md border ${
                status?.has_facebook_credentials 
                  ? 'bg-green-50 border-green-200' 
                  : 'bg-gray-50 border-gray-200'
              }`}>
                {status?.has_facebook_credentials ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <p className={`text-sm font-medium ${
                    status?.has_facebook_credentials ? 'text-green-800' : 'text-gray-800'
                  }`}>
                    Configure Facebook API
                  </p>
                  <p className="text-xs text-gray-500">
                    Add your Facebook Graph API key and Ad Account ID
                  </p>
                </div>
                {!status?.has_facebook_credentials && (
                  <ArrowRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
                )}
              </div>

              {/* Ad Analysis */}
              <div className={`flex items-center space-x-3 p-3 rounded-md border ${
                status?.has_analyzed_ads 
                  ? 'bg-green-50 border-green-200' 
                  : status?.has_facebook_credentials
                    ? 'bg-gray-50 border-gray-200'
                    : 'bg-gray-50 border-gray-200 opacity-50'
              }`}>
                {status?.has_analyzed_ads ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <p className={`text-sm font-medium ${
                    status?.has_analyzed_ads ? 'text-green-800' : 'text-gray-800'
                  }`}>
                    Run Ad Analysis
                  </p>
                  <p className="text-xs text-gray-500">
                    Analyze at least one Facebook ad
                  </p>
                </div>
                {!status?.has_analyzed_ads && status?.has_facebook_credentials && (
                  <ArrowRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            <button
              onClick={handlePrimaryAction}
              className="w-full flex items-center justify-center px-4 py-3 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              {!status?.has_facebook_credentials ? (
                <Settings className="h-4 w-4 mr-2" />
              ) : (
                <BarChart3 className="h-4 w-4 mr-2" />
              )}
              {nextAction}
            </button>

            <button
              onClick={retry}
              className="w-full flex items-center justify-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              Check Again
            </button>
          </div>

          {/* Logout Button */}
          <div className="mt-4">
            <button
              onClick={logout}
              className="w-full flex items-center justify-center px-4 py-2 border border-red-300 rounded-md shadow-sm text-sm font-medium text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors"
            >
              <LogOut className="h-4 w-4 mr-2" />
              Switch Account
            </button>
          </div>

          {/* Alternative Links */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="text-center space-y-2">
              <p className="text-xs text-gray-500">Quick links:</p>
              <div className="flex justify-center space-x-4 text-xs">
                <Link 
                  to="/settings" 
                  className="text-blue-600 hover:text-blue-500 hover:underline"
                >
                  Settings
                </Link>
                <Link 
                  to="/ad-analysis" 
                  className="text-blue-600 hover:text-blue-500 hover:underline"
                >
                  Ad Analysis
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Prerequisites are met, render the protected content
  return <>{children}</>;
};

export default PrerequisiteGuard; 