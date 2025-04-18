import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Loader2 } from 'lucide-react';

const SettingsForm: React.FC = () => {
  const { user, updateUserSettings, isLoading } = useAuth();
  
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
          Manage your Facebook API integration settings
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
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
        </CardContent>
        <CardFooter>
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
        </CardFooter>
      </form>
    </Card>
  );
};

export default SettingsForm;
