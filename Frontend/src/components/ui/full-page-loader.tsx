import { Loader2 } from 'lucide-react';

export const FullPageLoader = () => {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="flex items-center space-x-2">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="text-lg">Loading...</span>
      </div>
    </div>
  );
}; 