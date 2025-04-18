/** @jsxImportSource react */
import * as React from 'react';
import { useState, useEffect, useRef } from 'react';
import { Calendar } from '@/components/ui/calendar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { format } from 'date-fns';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useChat } from '@/contexts/ChatContext';

interface AnalysisSettingsPanelProps {
  isOpen: boolean;
  togglePanel: () => void;
}

const AnalysisSettingsPanel: React.FC<AnalysisSettingsPanelProps> = ({ isOpen, togglePanel }) => {
  const chatContext = useChat();
  const { updateDateRange, dateRange, sendMessage } = chatContext;
  const [startDate, setStartDate] = useState<Date | undefined>(
    dateRange.startDate ? new Date(dateRange.startDate) : undefined
  );
  const [endDate, setEndDate] = useState<Date | undefined>(
    dateRange.endDate ? new Date(dateRange.endDate) : undefined
  );
  const panelRef = useRef<HTMLDivElement>(null);

  // Update local state when dateRange changes from context
  useEffect(() => {
    console.log('Date range changed in context:', JSON.stringify(dateRange));
    if (dateRange.startDate) {
      setStartDate(new Date(dateRange.startDate));
    }
    if (dateRange.endDate) {
      setEndDate(new Date(dateRange.endDate));
    }
  }, [dateRange]);

  // Handle clicks outside the panel to close it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isOpen && 
          panelRef.current && 
          !panelRef.current.contains(event.target as Node) &&
          (event.target as Element).closest('button')?.getAttribute('data-panel-toggle') !== 'true') {
        togglePanel();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, togglePanel]);

  // Fix for empty object in localStorage - force setting the values directly
  const forceSetDateRange = (start: string, end: string) => {
    // 1. Update React state
    updateDateRange({
      startDate: start,
      endDate: end
    });
    
    // 2. Set directly to localStorage to bypass any potential state issues
    try {
      // Get the user ID from localStorage
      const authData = localStorage.getItem('auth');
      if (authData) {
        const parsedAuth = JSON.parse(authData);
        const userId = parsedAuth?.user?._id;
        
        if (userId) {
          console.log(`Forcing date range in localStorage for user ${userId}:`, { startDate: start, endDate: end });
          const dateRangeData = {
            startDate: start,
            endDate: end
          };
          
          localStorage.setItem(`dateRange_${userId}`, JSON.stringify(dateRangeData));
          localStorage.setItem('debug_dateRange', JSON.stringify(dateRangeData));
          
          // Also set to window global for debugging
          (window as any).forcedDateRange = dateRangeData;
          (window as any).CURRENT_DATE_RANGE = dateRangeData;
        }
      }
    } catch (e) {
      console.error('Error setting direct localStorage:', e);
    }
  };

  const handleApply = () => {
    if (startDate && endDate) {
      // Format dates in 'yyyy-MM-dd' format
      const formattedStart = format(startDate, 'yyyy-MM-dd');
      const formattedEnd = format(endDate, 'yyyy-MM-dd');
      
      console.log('Setting date range (before update):', { startDate: formattedStart, endDate: formattedEnd });
      
      // Force set the date range values directly
      forceSetDateRange(formattedStart, formattedEnd);
      
      // Store directly in localStorage as well for debugging
      localStorage.setItem('debug_dateRange', JSON.stringify({
        startDate: formattedStart,
        endDate: formattedEnd
      }));
      
      // Add a timeout to verify the state was updated
      setTimeout(() => {
        console.log('Current date range in context (after update):', JSON.stringify(dateRange));
        
        // Try to read what was saved to localStorage
        const userId = JSON.parse(localStorage.getItem('auth') || '{}')?.user?._id;
        if (userId) {
          const savedRange = localStorage.getItem(`dateRange_${userId}`);
          console.log('Saved in localStorage:', savedRange);
        }
      }, 100);
      
      togglePanel();
    }
  };

  // Calculate days between dates if both are selected
  const daysBetween = startDate && endDate
    ? Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div 
      className={`fixed right-0 top-0 h-full transition-all duration-300 ease-in-out z-50 ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      ref={panelRef}
    >
      <div className="absolute top-1/2 -left-8 transform -translate-y-1/2">
        <Button 
          variant="secondary" 
          size="icon" 
          onClick={togglePanel}
          className="h-8 w-8 rounded-full shadow-md"
          data-panel-toggle="true"
        >
          {isOpen ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>
      
      <Card className="h-full w-80 border-l border-t border-b rounded-l-lg rounded-r-none shadow-lg flex flex-col">
        <CardHeader>
          <CardTitle>Analysis Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto flex-grow">
          <div className="space-y-2">
            <h3 className="text-sm font-medium">Date Range</h3>
            <div className="space-y-2">
              <h4 className="text-xs text-muted-foreground">Start Date</h4>
              <Calendar
                mode="single"
                selected={startDate}
                onSelect={setStartDate}
                disabled={(date) => date > new Date() || (endDate ? date > endDate : false)}
                className="border rounded-md p-2"
              />
            </div>
            
            <div className="space-y-2">
              <h4 className="text-xs text-muted-foreground">End Date</h4>
              <Calendar
                mode="single"
                selected={endDate}
                onSelect={setEndDate}
                disabled={(date) => 
                  date > new Date() || 
                  (startDate ? date < startDate : false)
                }
                className="border rounded-md p-2"
              />
            </div>
          </div>
          
          {daysBetween !== null && (
            <div className="py-2 px-3 bg-muted rounded-md text-center">
              <p className="font-medium">{daysBetween} days selected</p>
              <p className="text-sm text-muted-foreground">
                {startDate && format(startDate, 'yyyy-MM-dd')} - {endDate && format(endDate, 'yyyy-MM-dd')}
              </p>
            </div>
          )}
          
          {/* Future settings can be added here */}
        </CardContent>
        <CardFooter className="flex-shrink-0">
          <Button 
            onClick={handleApply}
            disabled={!startDate || !endDate}
            className="w-full"
          >
            Apply Settings
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
};

export default AnalysisSettingsPanel; 