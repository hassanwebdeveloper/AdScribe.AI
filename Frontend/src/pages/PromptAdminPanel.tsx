import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { AlertCircle, Edit, Settings, Brain, Eye, LogOut, User, Plus, Trash2, RotateCcw } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface PromptTemplate {
  id: string;
  prompt_key: string;
  prompt_name: string;
  prompt_text: string;
  variables: string[];
  model: string;
  temperature: number;
  max_tokens: number | null;
  description: string;
  category: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

interface PromptTemplateUpdate {
  prompt_name?: string;
  prompt_text?: string;
  variables?: string[];
  model?: string;
  temperature?: number;
  max_tokens?: number | null;
  description?: string;
  category?: string;
}

interface ClassificationClasses {
  id: string;
  name: string;
  description: string;
  classes: Record<string, string>;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

interface ClassificationClassesCreate {
  name: string;
  description: string;
  classes: Record<string, string>;
}

interface ClassificationClassesUpdate {
  name?: string;
  description?: string;
  classes?: Record<string, string>;
  is_active?: boolean;
}

const PromptAdminPanel: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [adminEmail, setAdminEmail] = useState<string>('');
  
  // Classification Classes state
  const [classificationClasses, setClassificationClasses] = useState<ClassificationClasses[]>([]);
  const [selectedClassificationClasses, setSelectedClassificationClasses] = useState<ClassificationClasses | null>(null);
  const [classificationDialogOpen, setClassificationDialogOpen] = useState(false);
  const [isCreatingClassification, setIsCreatingClassification] = useState(false);
  
  const navigate = useNavigate();

  const [formData, setFormData] = useState<PromptTemplateUpdate>({
    prompt_name: '',
    prompt_text: '',
    variables: [],
    model: 'gpt-4o',
    temperature: 0.4,
    max_tokens: null,
    description: '',
    category: 'general'
  });

  const [classificationFormData, setClassificationFormData] = useState<ClassificationClassesCreate>({
    name: '',
    description: '',
    classes: {}
  });

  // Use relative URL so it works with frontend dev server proxy
  const API_BASE = '/api/v1/admin';

  useEffect(() => {
    checkAuthAndFetchData();
  }, []);

  const checkAuthAndFetchData = async () => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      navigate('/admin/login');
      return;
    }

    try {
      // Verify session
      const authResponse = await fetch(`${API_BASE}/auth/verify-session`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!authResponse.ok) {
        localStorage.removeItem('admin_token');
        navigate('/admin/login');
        return;
      }

      const authData = await authResponse.json();
      setAdminEmail(authData.email);

      // If auth is valid, fetch data
      await Promise.all([fetchPrompts(), fetchModels(), fetchClassificationClasses()]);
    } catch (err) {
      localStorage.removeItem('admin_token');
      navigate('/admin/login');
    }
  };

  // Helper function to get auth headers
  const getAuthHeaders = () => {
    const token = localStorage.getItem('admin_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
  };

  const fetchPrompts = async () => {
    try {
      const response = await fetch(`${API_BASE}/prompts`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        throw new Error('Failed to fetch prompts');
      }
      const data = await response.json();
      setPrompts(Array.isArray(data) ? data : []);
    } catch (err) {
      setError('Failed to load prompts: ' + err.message);
      setPrompts([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchModels = async () => {
    try {
      const response = await fetch(`${API_BASE}/models`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        throw new Error('Failed to fetch models');
      }
      const data = await response.json();
      setModels(Array.isArray(data.models) ? data.models : []);
    } catch (err) {
      console.error('Failed to load models:', err);
      setModels([]);
    }
  };

  const fetchClassificationClasses = async () => {
    try {
      const response = await fetch(`${API_BASE}/classification-classes`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        throw new Error('Failed to fetch classification classes');
      }
      const data = await response.json();
      setClassificationClasses(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load classification classes:', err);
      setClassificationClasses([]);
    }
  };

  const extractVariables = (text: string): string[] => {
    const matches = text.match(/\{([^}]+)\}/g);
    if (!matches) return [];
    return [...new Set(matches.map(match => match.slice(1, -1)))];
  };

  const handleEdit = (prompt: PromptTemplate) => {
    setSelectedPrompt(prompt);
    setFormData({
      prompt_name: prompt.prompt_name,
      prompt_text: prompt.prompt_text,
      variables: prompt.variables,
      model: prompt.model,
      temperature: prompt.temperature,
      max_tokens: prompt.max_tokens,
      description: prompt.description,
      category: prompt.category
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!selectedPrompt) return;
    
    try {
      // Auto-extract variables from prompt text
      const variables = extractVariables(formData.prompt_text || '');
      const dataToSend = { ...formData, variables };

      const response = await fetch(`${API_BASE}/prompts/${selectedPrompt.prompt_key}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(dataToSend)
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save prompt');
      }

      await fetchPrompts();
      setDialogOpen(false);
      setError(null);
    } catch (err) {
      setError('Failed to save: ' + err.message);
    }
  };

  const initializeDefaults = async () => {
    try {
      const response = await fetch(`${API_BASE}/prompts/initialize-defaults`, {
        method: 'POST',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        throw new Error('Failed to initialize defaults');
      }

      await fetchPrompts();
      setError(null);
    } catch (err) {
      setError('Failed to initialize defaults: ' + err.message);
    }
  };

  const initializeDefaultPrompt = async (promptKey: string) => {
    try {
      const response = await fetch(`${API_BASE}/prompts/${promptKey}/initialize-default`, {
        method: 'POST',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        throw new Error('Failed to initialize default prompt');
      }

      await fetchPrompts();
      setError(null);
    } catch (err) {
      setError(`Failed to initialize default prompt: ${err.message}`);
    }
  };

  const handleCreateClassification = () => {
    setIsCreatingClassification(true);
    setSelectedClassificationClasses(null);
    setClassificationFormData({
      name: '',
      description: '',
      classes: {}
    });
    setClassificationDialogOpen(true);
  };

  const handleEditClassification = (classification: ClassificationClasses) => {
    setIsCreatingClassification(false);
    setSelectedClassificationClasses(classification);
    setClassificationFormData({
      name: classification.name,
      description: classification.description,
      classes: { ...classification.classes }
    });
    setClassificationDialogOpen(true);
  };

  const handleSaveClassification = async () => {
    try {
      const url = isCreatingClassification 
        ? `${API_BASE}/classification-classes`
        : `${API_BASE}/classification-classes/${selectedClassificationClasses?.name}`;
      
      const method = isCreatingClassification ? 'POST' : 'PUT';

      const response = await fetch(url, {
        method,
        headers: getAuthHeaders(),
        body: JSON.stringify(classificationFormData)
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save classification classes');
      }

      await fetchClassificationClasses();
      setClassificationDialogOpen(false);
      setError(null);
    } catch (err) {
      setError('Failed to save classification classes: ' + err.message);
    }
  };

  const handleDeleteClassification = async (name: string) => {
    if (!confirm('Are you sure you want to delete these classification classes?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/classification-classes/${name}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('admin_token');
          navigate('/admin/login');
          return;
        }
        throw new Error('Failed to delete classification classes');
      }

      await fetchClassificationClasses();
      setError(null);
    } catch (err) {
      setError('Failed to delete classification classes: ' + err.message);
    }
  };

  const addClassificationClass = () => {
    const newClasses = { ...classificationFormData.classes };
    newClasses[`class_${Object.keys(newClasses).length + 1}`] = '';
    setClassificationFormData({ ...classificationFormData, classes: newClasses });
  };

  const updateClassificationClass = (oldKey: string, newKey: string, value: string) => {
    const newClasses = { ...classificationFormData.classes };
    if (oldKey !== newKey && newKey in newClasses) {
      alert('Class name already exists!');
      return;
    }
    
    delete newClasses[oldKey];
    newClasses[newKey] = value;
    setClassificationFormData({ ...classificationFormData, classes: newClasses });
  };

  const removeClassificationClass = (key: string) => {
    const newClasses = { ...classificationFormData.classes };
    delete newClasses[key];
    setClassificationFormData({ ...classificationFormData, classes: newClasses });
  };

  const handleLogout = async () => {
    try {
      const token = localStorage.getItem('admin_token');
      if (token) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      localStorage.removeItem('admin_token');
      navigate('/admin/login');
    }
  };

  const groupedPrompts = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.category]) acc[prompt.category] = [];
    acc[prompt.category].push(prompt);
    return acc;
  }, {} as Record<string, PromptTemplate[]>);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading prompts...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                <Settings className="h-8 w-8 text-blue-600" />
                Prompt Admin Panel
              </h1>
              <p className="text-gray-600 mt-2">
                Manage OpenAI prompts, classification classes, and model selections for the AI system
              </p>
            </div>
            <div className="flex items-center gap-4">
              {adminEmail && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <User className="h-4 w-4" />
                  <span>{adminEmail}</span>
                </div>
              )}
              <Button onClick={initializeDefaults} variant="outline">
                Initialize All Defaults
              </Button>
              <Button onClick={handleLogout} variant="outline" className="text-red-600 hover:text-red-700">
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-700">{error}</AlertDescription>
          </Alert>
        )}

        {/* Main Content Tabs */}
        <Tabs defaultValue="prompts" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="prompts">
              <Brain className="h-4 w-4 mr-2" />
              Prompts ({prompts.length})
            </TabsTrigger>
            <TabsTrigger value="classification">
              <AlertCircle className="h-4 w-4 mr-2" />
              Classification Classes ({classificationClasses.length})
            </TabsTrigger>
          </TabsList>

          {/* Prompts Tab */}
          <TabsContent value="prompts" className="mt-6">
            <Tabs defaultValue="all" className="w-full">
                             <TabsList className="grid w-full grid-cols-5">
                 <TabsTrigger value="all">All Prompts ({prompts.length})</TabsTrigger>
                 {Object.keys(groupedPrompts).map(category => (
                   <TabsTrigger key={category} value={category}>
                     {category.charAt(0).toUpperCase() + category.slice(1)} ({(groupedPrompts[category] || []).length})
                   </TabsTrigger>
                 ))}
               </TabsList>

              <TabsContent value="all" className="mt-6">
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {prompts.map(prompt => (
                    <PromptCard 
                      key={prompt.id} 
                      prompt={prompt} 
                      onEdit={handleEdit}
                      onInitializeDefault={initializeDefaultPrompt}
                    />
                  ))}
                </div>
              </TabsContent>

                             {Object.entries(groupedPrompts).map(([category, categoryPrompts]) => (
                 <TabsContent key={category} value={category} className="mt-6">
                   <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                     {(categoryPrompts || []).map(prompt => (
                       <PromptCard 
                         key={prompt.id} 
                         prompt={prompt} 
                         onEdit={handleEdit}
                         onInitializeDefault={initializeDefaultPrompt}
                       />
                     ))}
                   </div>
                 </TabsContent>
               ))}
            </Tabs>
          </TabsContent>

          {/* Classification Classes Tab */}
          <TabsContent value="classification" className="mt-6">
            <div className="mb-6 flex justify-between items-center">
              <div>
                <h2 className="text-xl font-semibold">Classification Classes</h2>
                <p className="text-gray-600">Manage text classification categories used in prompts</p>
              </div>
              <Button onClick={handleCreateClassification}>
                <Plus className="h-4 w-4 mr-2" />
                Add Classification Set
              </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {classificationClasses.map(classification => (
                <ClassificationCard 
                  key={classification.id} 
                  classification={classification} 
                  onEdit={handleEditClassification}
                  onDelete={handleDeleteClassification}
                />
              ))}
            </div>
          </TabsContent>
        </Tabs>

        {/* Prompt Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit Prompt</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="prompt_key">Prompt Key</Label>
                  <Input
                    id="prompt_key"
                    value={selectedPrompt?.prompt_key || ''}
                    disabled
                    className="bg-gray-100"
                  />
                </div>
                <div>
                  <Label htmlFor="prompt_name">Prompt Name</Label>
                  <Input
                    id="prompt_name"
                    value={formData.prompt_name || ''}
                    onChange={(e) => setFormData({ ...formData, prompt_name: e.target.value })}
                    placeholder="e.g., Ad Script Generator"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="What does this prompt do?"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="category">Category</Label>
                  <Input
                    id="category"
                    value={formData.category || ''}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    placeholder="e.g., ad_generation, analysis"
                  />
                </div>
                <div>
                  <Label htmlFor="model">Model</Label>
                  <Select value={formData.model} onValueChange={(value) => setFormData({ ...formData, model: value })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                                         <SelectContent>
                       {(models || []).map(model => (
                         <SelectItem key={model} value={model}>{model}</SelectItem>
                       ))}
                     </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="temperature">Temperature</Label>
                  <Input
                    id="temperature"
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    value={formData.temperature || 0.4}
                    onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                  />
                </div>
                <div>
                  <Label htmlFor="max_tokens">Max Tokens</Label>
                  <Input
                    id="max_tokens"
                    type="number"
                    min="1"
                    value={formData.max_tokens || ''}
                    onChange={(e) => setFormData({ ...formData, max_tokens: e.target.value ? parseInt(e.target.value) : null })}
                    placeholder="Leave empty for no limit"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="prompt_text">Prompt Text</Label>
                <Textarea
                  id="prompt_text"
                  value={formData.prompt_text || ''}
                  onChange={(e) => setFormData({ ...formData, prompt_text: e.target.value })}
                  className="min-h-[200px] font-mono text-sm"
                  placeholder="Enter your prompt template here..."
                />
              </div>

              {formData.prompt_text && (
                <div>
                  <Label>Detected Variables</Label>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {extractVariables(formData.prompt_text).map(variable => (
                      <Badge key={variable} variant="secondary">
                        {variable}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSave}>
                  Save Changes
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Classification Classes Edit Dialog */}
        <Dialog open={classificationDialogOpen} onOpenChange={setClassificationDialogOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {isCreatingClassification ? 'Create Classification Classes' : 'Edit Classification Classes'}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="classification_name">Name</Label>
                  <Input
                    id="classification_name"
                    value={classificationFormData.name}
                    onChange={(e) => setClassificationFormData({ ...classificationFormData, name: e.target.value })}
                    placeholder="e.g., ad_script_generator"
                    disabled={!isCreatingClassification}
                  />
                </div>
                <div>
                  <Label htmlFor="classification_description">Description</Label>
                  <Input
                    id="classification_description"
                    value={classificationFormData.description}
                    onChange={(e) => setClassificationFormData({ ...classificationFormData, description: e.target.value })}
                    placeholder="What is this classification set for?"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-4">
                  <Label>Classification Classes</Label>
                  <Button onClick={addClassificationClass} size="sm">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Class
                  </Button>
                </div>
                
                <div className="space-y-3">
                  {Object.entries(classificationFormData.classes).map(([key, value]) => (
                    <div key={key} className="flex gap-2 items-center">
                      <Input
                        placeholder="Class name (e.g., ad_script)"
                        value={key}
                        onChange={(e) => updateClassificationClass(key, e.target.value, value)}
                        className="w-1/3"
                      />
                      <Input
                        placeholder="Class description"
                        value={value}
                        onChange={(e) => updateClassificationClass(key, key, e.target.value)}
                        className="flex-1"
                      />
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => removeClassificationClass(key)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  
                  {Object.keys(classificationFormData.classes).length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      No classification classes yet. Click "Add Class" to get started.
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setClassificationDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSaveClassification}>
                  {isCreatingClassification ? 'Create' : 'Save Changes'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

interface PromptCardProps {
  prompt: PromptTemplate;
  onEdit: (prompt: PromptTemplate) => void;
  onInitializeDefault: (promptKey: string) => void;
}

const PromptCard: React.FC<PromptCardProps> = ({ prompt, onEdit, onInitializeDefault }) => {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg mb-1">{prompt.prompt_name}</CardTitle>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline">{prompt.prompt_key}</Badge>
              <Badge variant="secondary">{prompt.category}</Badge>
            </div>
          </div>
        </div>
        <p className="text-sm text-gray-600 line-clamp-2">{prompt.description}</p>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Model:</span>
              <p className="text-gray-600">{prompt.model}</p>
            </div>
            <div>
              <span className="font-medium text-gray-700">Temperature:</span>
              <p className="text-gray-600">{prompt.temperature}</p>
            </div>
            <div>
              <span className="font-medium text-gray-700">Max Tokens:</span>
              <p className="text-gray-600">{prompt.max_tokens || 'No limit'}</p>
            </div>
            <div>
              <span className="font-medium text-gray-700">Variables:</span>
              <p className="text-gray-600">{prompt.variables.length}</p>
            </div>
          </div>

          {prompt.variables.length > 0 && (
            <div>
              <span className="text-sm font-medium text-gray-700">Variables:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {prompt.variables.slice(0, 4).map(variable => (
                  <Badge key={variable} variant="outline" className="text-xs">
                    {variable}
                  </Badge>
                ))}
                {prompt.variables.length > 4 && (
                  <Badge variant="outline" className="text-xs">
                    +{prompt.variables.length - 4} more
                  </Badge>
                )}
              </div>
            </div>
          )}
          
          <div className="flex gap-2">
            <Button onClick={() => onEdit(prompt)} size="sm" className="flex-1">
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button 
              onClick={() => onInitializeDefault(prompt.prompt_key)} 
              size="sm" 
              variant="outline"
              title="Reset to default"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

interface ClassificationCardProps {
  classification: ClassificationClasses;
  onEdit: (classification: ClassificationClasses) => void;
  onDelete: (name: string) => void;
}

const ClassificationCard: React.FC<ClassificationCardProps> = ({ classification, onEdit, onDelete }) => {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg mb-1">{classification.name}</CardTitle>
            <p className="text-sm text-gray-600 line-clamp-2">{classification.description}</p>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="space-y-3">
          <div>
            <span className="text-sm font-medium text-gray-700">Classes ({Object.keys(classification.classes).length}):</span>
            <div className="mt-2 space-y-1">
              {Object.entries(classification.classes).slice(0, 3).map(([key, value]) => (
                <div key={key} className="text-xs">
                  <span className="font-medium">{key}:</span> {value.length > 50 ? value.substring(0, 50) + '...' : value}
                </div>
              ))}
              {Object.keys(classification.classes).length > 3 && (
                <div className="text-xs text-gray-500">
                  +{Object.keys(classification.classes).length - 3} more classes
                </div>
              )}
            </div>
          </div>
          
          <div className="flex gap-2">
            <Button onClick={() => onEdit(classification)} size="sm" className="flex-1">
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button 
              onClick={() => onDelete(classification.name)} 
              size="sm" 
              variant="outline"
              className="text-red-600 hover:text-red-700"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default PromptAdminPanel; 