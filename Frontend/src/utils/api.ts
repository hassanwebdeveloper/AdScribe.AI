import axios from 'axios';
import { useToast } from '@/components/ui/use-toast';

// Create a toast function for the interceptor
const showToast = (props: { title: string; description: string; variant: 'default' | 'destructive' }) => {
  // This is a bit of a hack since we're outside React's component tree
  // In a real app, you'd want to use a global toast state manager
  const toastEvent = new CustomEvent('show-toast', { detail: props });
  window.dispatchEvent(toastEvent);
};

// Create an axios instance that includes the auth token with each request
const api = axios.create({
  baseURL: '/api/v1',
});

// Add a request interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    } else {
      console.warn('No authentication token found. Request may fail if authentication is required.');
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor to handle common error cases
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle 401 errors (unauthorized)
    if (error.response && error.response.status === 401) {
      console.error('Authentication error: Session expired or invalid token');
      
      // Log the error to console
      console.error('Authentication error details:', error.response.data);
      
      // Redirect to login page after a short delay
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    }
    
    // Handle 403 errors (forbidden)
    if (error.response && error.response.status === 403) {
      console.error('Authorization error: Insufficient permissions');
    }
    
    return Promise.reject(error);
  }
);

export default api; 