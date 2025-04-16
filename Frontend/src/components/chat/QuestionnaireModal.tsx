
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useChat } from '@/contexts/ChatContext';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

const QuestionnaireModal: React.FC = () => {
  const { updateQuestionnaire, questionnaire, submitQuestionnaire, processingQuestionnaire } = useChat();
  const [step, setStep] = useState(1);
  
  const totalSteps = 5;
  
  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      submitQuestionnaire();
    }
  };
  
  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };
  
  const renderQuestion = () => {
    switch (step) {
      case 1:
        return (
          <>
            <Label htmlFor="adObjective" className="font-medium mb-1">
              What is the main objective of your Facebook ad?
            </Label>
            <Textarea
              id="adObjective"
              placeholder="e.g., Lead generation, Brand awareness, Direct sales..."
              value={questionnaire.adObjective || ''}
              onChange={(e) => updateQuestionnaire({ adObjective: e.target.value })}
              className="min-h-[100px]"
            />
          </>
        );
      
      case 2:
        return (
          <>
            <Label htmlFor="targetAudience" className="font-medium mb-1">
              Describe your target audience in detail
            </Label>
            <Textarea
              id="targetAudience"
              placeholder="e.g., Age range, interests, demographics, pain points..."
              value={questionnaire.targetAudience || ''}
              onChange={(e) => updateQuestionnaire({ targetAudience: e.target.value })}
              className="min-h-[100px]"
            />
          </>
        );
      
      case 3:
        return (
          <>
            <Label htmlFor="adBudget" className="font-medium mb-1">
              What's your budget for this ad campaign?
            </Label>
            <Textarea
              id="adBudget"
              placeholder="e.g., Daily budget, total campaign budget..."
              value={questionnaire.adBudget || ''}
              onChange={(e) => updateQuestionnaire({ adBudget: e.target.value })}
              className="min-h-[100px]"
            />
          </>
        );
      
      case 4:
        return (
          <>
            <Label htmlFor="productFeatures" className="font-medium mb-1">
              What are the key features or benefits of your product/service?
            </Label>
            <Textarea
              id="productFeatures"
              placeholder="e.g., Saves time, increases efficiency, award-winning design..."
              value={questionnaire.productFeatures || ''}
              onChange={(e) => updateQuestionnaire({ productFeatures: e.target.value })}
              className="min-h-[100px]"
            />
          </>
        );
      
      case 5:
        return (
          <>
            <Label htmlFor="competitorInfo" className="font-medium mb-1">
              What sets you apart from competitors?
            </Label>
            <Textarea
              id="competitorInfo"
              placeholder="e.g., Unique features, better pricing, faster service..."
              value={questionnaire.competitorInfo || ''}
              onChange={(e) => updateQuestionnaire({ competitorInfo: e.target.value })}
              className="min-h-[100px]"
            />
          </>
        );
      
      default:
        return null;
    }
  };
  
  return (
    <Card className="w-full max-w-lg mx-auto animate-bounce-in">
      <CardHeader>
        <CardTitle>Tell me about your Facebook Ad needs</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex justify-between mb-4 text-sm text-muted-foreground">
          <span>Step {step} of {totalSteps}</span>
          <span>{Math.round((step / totalSteps) * 100)}% complete</span>
        </div>
        <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
          <div 
            className="bg-brand-500 h-full transition-all duration-300 ease-out"
            style={{ width: `${(step / totalSteps) * 100}%` }}
          ></div>
        </div>
        
        <div className="space-y-2 my-6">
          {renderQuestion()}
        </div>
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button 
          variant="outline" 
          onClick={handleBack}
          disabled={step === 1 || processingQuestionnaire}
        >
          Back
        </Button>
        <Button 
          onClick={handleNext}
          disabled={
            (step === 1 && !questionnaire.adObjective) || 
            (step === 2 && !questionnaire.targetAudience) ||
            (step === 3 && !questionnaire.adBudget) ||
            (step === 4 && !questionnaire.productFeatures) ||
            (step === 5 && !questionnaire.competitorInfo) ||
            processingQuestionnaire
          }
        >
          {processingQuestionnaire ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : step === totalSteps ? (
            'Submit'
          ) : (
            'Next'
          )}
        </Button>
      </CardFooter>
    </Card>
  );
};

export default QuestionnaireModal;
