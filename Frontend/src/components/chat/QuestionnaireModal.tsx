import React from 'react';
import { Button } from '@/components/ui/button';
import { useChat } from '@/contexts/ChatContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

const QuestionnaireModal: React.FC = () => {
  const { updateQuestionnaire, questionnaire, submitQuestionnaire, processingQuestionnaire } = useChat();
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submitQuestionnaire();
  };
  
  return (
    <Card className="w-full max-w-lg mx-auto animate-bounce-in">
      <CardHeader>
        <CardTitle>Before we start</CardTitle>
        <CardDescription>We need a bit of information to help analyze your Facebook Ads data.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="daysToAnalyze" className="font-medium">
              How many previous days of data would you like to analyze?
            </Label>
            <Input
              id="daysToAnalyze"
              type="number"
              min="1"
              max="90"
              placeholder="e.g., 30"
              value={questionnaire.daysToAnalyze || ''}
              onChange={(e) => updateQuestionnaire({ daysToAnalyze: e.target.value })}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Enter a number between 1 and 90 days. We recommend at least 30 days for meaningful insights.
            </p>
          </div>
        </CardContent>
        <CardFooter className="flex justify-end">
          <Button 
            type="submit"
            disabled={!questionnaire.daysToAnalyze || processingQuestionnaire}
          >
            {processingQuestionnaire ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              'Start Analysis'
            )}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
};

export default QuestionnaireModal;
