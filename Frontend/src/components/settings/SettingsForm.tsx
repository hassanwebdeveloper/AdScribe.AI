import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Loader2, Facebook } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const SettingsForm: React.FC = () => {
  const { user, updateUserSettings, handleFacebookLogin, isLoading } = useAuth();
  
  const [fbGraphApiKey, setFbGraphApiKey] = useState('');
  const [fbAdAccountId, setFbAdAccountId] = useState('');
  
  // When user data changes, update the form fields
  useEffect(() => {
    if (user) {
      setFbGraphApiKey(user.fbGraphApiKey || '');
      setFbAdAccountId(user.fbAdAccountId || '');
    }
  }, [user]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateUserSettings({
      fbGraphApiKey,
      fbAdAccountId,
    });
  };
  
  return (
    <Card className="w-full max-w-lg mx-auto">
      <CardHeader>
        <CardTitle>API Settings</CardTitle>
        <CardDescription>
          Choose how you want to connect your Facebook account
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="manual" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="manual">Manual Setup</TabsTrigger>
            <TabsTrigger value="oauth">Facebook OAuth</TabsTrigger>
          </TabsList>
          
          <TabsContent value="manual">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fbGraphApiKey">Facebook Graph API Key</Label>
                <Input
                  id="fbGraphApiKey"
                  type="password"
                  value={fbGraphApiKey}
                  onChange={(e) => setFbGraphApiKey(e.target.value)}
                  placeholder="Enter your Facebook Graph API key"
                />
                <p className="text-xs text-muted-foreground">
                  Your API key is stored securely and is required to access your Facebook Ad data.
                </p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="fbAdAccountId">Facebook Ad Manager Account ID</Label>
                <Input
                  id="fbAdAccountId"
                  value={fbAdAccountId}
                  onChange={(e) => setFbAdAccountId(e.target.value)}
                  placeholder="Enter your Facebook Ad Manager Account ID"
                />
                <p className="text-xs text-muted-foreground">
                  This ID is used to identify your Ad Manager account when pulling reports and data.
                </p>
              </div>
              
              <Button type="submit" disabled={isLoading} className="w-full">
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Updating...
                  </>
                ) : (
                  'Save Settings'
                )}
              </Button>
            </form>
          </TabsContent>
          
          <TabsContent value="oauth">
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Connect your Facebook account securely using OAuth. This will allow us to access your ad data without storing your API key.
              </p>
              <Button 
                type="button" 
                variant="outline" 
                className="w-full flex items-center justify-center gap-2"
                onClick={handleFacebookLogin}
                disabled={isLoading}
              >
                <Facebook className="h-5 w-5 text-blue-600" />
                <span>Connect with Facebook</span>
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

export default SettingsForm;
