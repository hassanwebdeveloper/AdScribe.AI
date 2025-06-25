import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  TrendingUp, 
  TrendingDown,
  DollarSign,
  Target,
  Users,
  Eye,
  ShoppingCart,
  Clock,
  AlertTriangle,
  CheckCircle,
  Info
} from 'lucide-react';

interface ParameterChange {
  current: number;
  optimized: number;
  change_percent: number;
  change_direction: 'increase' | 'decrease';
  ai_suggestion: string;
  priority: 'High' | 'Medium' | 'Low';
  implementation_difficulty: 'Easy' | 'Medium' | 'Hard';
  expected_timeline: string;
}

interface AdParameterDialogProps {
  isOpen: boolean;
  onClose: () => void;
  adData: {
    ad_id: string;
    ad_name: string;
    all_parameter_changes: Record<string, ParameterChange>;
    expected_roas_improvement: string;
    current_roas?: number;
    predicted_roas?: number;
  } | null;
}

const AdParameterDialog: React.FC<AdParameterDialogProps> = ({
  isOpen,
  onClose,
  adData
}) => {
  if (!adData) return null;

  const getParameterIcon = (param: string) => {
    const icons: Record<string, React.ReactNode> = {
      ctr: <Target className="h-4 w-4" />,
      spend: <DollarSign className="h-4 w-4" />,
      cpc: <DollarSign className="h-4 w-4" />,
      cpm: <DollarSign className="h-4 w-4" />,
      clicks: <Users className="h-4 w-4" />,
      impressions: <Eye className="h-4 w-4" />,
      purchases: <ShoppingCart className="h-4 w-4" />
    };
    return icons[param] || <Info className="h-4 w-4" />;
  };

  const getParameterDisplayName = (param: string) => {
    const names: Record<string, string> = {
      ctr: 'Click-Through Rate',
      spend: 'Daily Spend',
      cpc: 'Cost Per Click',
      cpm: 'Cost Per Mille',
      clicks: 'Total Clicks',
      impressions: 'Impressions',
      purchases: 'Purchases/Conversions'
    };
    return names[param] || param.toUpperCase();
  };

  const getParameterUnit = (param: string) => {
    const units: Record<string, string> = {
      ctr: '%',
      spend: '$',
      cpc: '$',
      cpm: '$',
      clicks: '',
      impressions: '',
      purchases: ''
    };
    return units[param] || '';
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'High': return 'bg-red-100 text-red-800 border-red-200';
      case 'Medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'Easy': return 'bg-green-100 text-green-800 border-green-200';
      case 'Medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Hard': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const formatValue = (param: string, value: number) => {
    const unit = getParameterUnit(param);
    if (param === 'spend' || param === 'cpc' || param === 'cpm') {
      return `${unit}${value.toFixed(2)}`;
    } else if (param === 'ctr') {
      return `${value.toFixed(2)}${unit}`;
    } else {
      return `${Math.round(value)}${unit}`;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            {adData.ad_name}
          </DialogTitle>
          <DialogDescription>
            Detailed parameter optimization recommendations with AI insights
          </DialogDescription>
        </DialogHeader>

        {/* ROAS Overview */}
        <Card className="mb-6 bg-gradient-to-r from-blue-50 to-purple-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-green-600" />
              ROAS Improvement
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-sm text-muted-foreground">Current ROAS</p>
                <p className="text-2xl font-bold">{adData.current_roas?.toFixed(2) || 'N/A'}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Predicted ROAS</p>
                <p className="text-2xl font-bold text-green-600">{adData.predicted_roas?.toFixed(2) || 'N/A'}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Improvement</p>
                <p className="text-2xl font-bold text-green-600">+{adData.expected_roas_improvement}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Parameter Changes */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Parameter Changes Required</h3>
          
          {Object.entries(adData.all_parameter_changes).map(([param, change]) => (
            <Card key={param} className="border-l-4 border-l-blue-500">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getParameterIcon(param)}
                    {getParameterDisplayName(param)}
                  </div>
                  <div className="flex gap-2">
                    <Badge className={getPriorityColor(change.priority)}>
                      {change.priority} Priority
                    </Badge>
                    <Badge className={getDifficultyColor(change.implementation_difficulty)}>
                      {change.implementation_difficulty}
                    </Badge>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Value Changes */}
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-sm text-muted-foreground">Current</p>
                    <p className="text-xl font-bold">{formatValue(param, change.current)}</p>
                  </div>
                  <div className="flex items-center justify-center">
                    {change.change_direction === 'increase' ? (
                      <TrendingUp className="h-6 w-6 text-green-600" />
                    ) : (
                      <TrendingDown className="h-6 w-6 text-red-600" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Target</p>
                    <p className={`text-xl font-bold ${
                      change.change_direction === 'increase' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {formatValue(param, change.optimized)}
                    </p>
                  </div>
                </div>

                {/* Change Percentage */}
                <div className="text-center">
                  <Badge variant="outline" className="text-sm">
                    {change.change_direction === 'increase' ? '+' : ''}{change.change_percent.toFixed(1)}% change required
                  </Badge>
                </div>

                <Separator />

                {/* AI Suggestion */}
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="flex items-start gap-2">
                    <div className="bg-blue-100 p-1 rounded">
                      <Info className="h-4 w-4 text-blue-600" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-blue-900 mb-1">AI Recommendation</p>
                      <p className="text-sm text-blue-800">{change.ai_suggestion}</p>
                    </div>
                  </div>
                </div>

                {/* Implementation Details */}
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    <span>Expected timeline: {change.expected_timeline}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {change.implementation_difficulty === 'Easy' && <CheckCircle className="h-4 w-4 text-green-600" />}
                    {change.implementation_difficulty === 'Medium' && <AlertTriangle className="h-4 w-4 text-yellow-600" />}
                    {change.implementation_difficulty === 'Hard' && <AlertTriangle className="h-4 w-4 text-red-600" />}
                    <span>Implementation: {change.implementation_difficulty}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Implementation Priority */}
        <Card className="mt-6 bg-amber-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              Implementation Order
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Recommended order based on priority and difficulty:
            </p>
            <ol className="space-y-2 text-sm">
              {Object.entries(adData.all_parameter_changes)
                .sort((a, b) => {
                  const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
                  const difficultyOrder = { 'Easy': 3, 'Medium': 2, 'Hard': 1 };
                  
                  const scoreA = priorityOrder[a[1].priority as keyof typeof priorityOrder] + 
                                difficultyOrder[a[1].implementation_difficulty as keyof typeof difficultyOrder];
                  const scoreB = priorityOrder[b[1].priority as keyof typeof priorityOrder] + 
                                difficultyOrder[b[1].implementation_difficulty as keyof typeof difficultyOrder];
                  
                  return scoreB - scoreA;
                })
                .map(([param, change], index) => (
                  <li key={param} className="flex items-center gap-2">
                    <span className="bg-amber-100 text-amber-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">
                      {index + 1}
                    </span>
                    <span>{getParameterDisplayName(param)}</span>
                    <Badge size="sm" className={getPriorityColor(change.priority)}>
                      {change.priority}
                    </Badge>
                    <Badge size="sm" className={getDifficultyColor(change.implementation_difficulty)}>
                      {change.implementation_difficulty}
                    </Badge>
                  </li>
                ))}
            </ol>
          </CardContent>
        </Card>
      </DialogContent>
    </Dialog>
  );
};

export default AdParameterDialog; 