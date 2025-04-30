import React, { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Navigate } from 'react-router-dom';
import { Facebook } from 'lucide-react';
import { FacebookAdAccount } from '@/types';

const SelectAdAccount: React.FC = () => {
  const { isAuthenticated, user, getFacebookAdAccounts, setFacebookAdAccount, isLoading } = useAuth();
  const [adAccounts, setAdAccounts] = useState<FacebookAdAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [fetchingAccounts, setFetchingAccounts] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  // Redirect to dashboard if already has ad account set
  if (user?.facebook_credentials?.account_id) {
    return <Navigate to="/dashboard" />;
  }

  useEffect(() => {
    const fetchAdAccounts = async () => {
      setFetchingAccounts(true);
      setError(null);
      try {
        const accounts = await getFacebookAdAccounts();
        setAdAccounts(accounts);
        if (accounts.length > 0) {
          setSelectedAccountId(accounts[0].id);
        }
      } catch (error) {
        setError('Failed to fetch ad accounts. Please try again.');
      } finally {
        setFetchingAccounts(false);
      }
    };

    fetchAdAccounts();
  }, [getFacebookAdAccounts]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedAccountId) {
      await setFacebookAdAccount(selectedAccountId);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12 sm:px-6 lg:px-8 bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-2 mb-2">
            <Facebook className="h-6 w-6 text-blue-600" />
            <CardTitle className="text-2xl font-bold">Select Ad Account</CardTitle>
          </div>
          <CardDescription>
            Choose which Facebook Ad Account you want to use with AdScribe AI
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {fetchingAccounts ? (
              <div className="text-center py-4">Loading ad accounts...</div>
            ) : error ? (
              <div className="text-destructive text-center py-4">{error}</div>
            ) : adAccounts.length === 0 ? (
              <div className="text-center py-4">
                No ad accounts found. Please make sure you have access to Facebook Ad accounts.
              </div>
            ) : (
              <RadioGroup
                value={selectedAccountId}
                onValueChange={setSelectedAccountId}
                className="space-y-2"
              >
                {adAccounts.map((account) => (
                  <div
                    key={account.id}
                    className="flex items-center space-x-2 border p-3 rounded-md hover:bg-gray-50"
                  >
                    <RadioGroupItem value={account.id} id={account.id} />
                    <Label
                      htmlFor={account.id}
                      className="flex-1 cursor-pointer flex flex-col"
                    >
                      <span className="font-medium">{account.name}</span>
                      <span className="text-sm text-gray-500">ID: {account.id}</span>
                    </Label>
                    <div className="text-xs px-2 py-1 rounded-full bg-gray-100">
                      {account.account_status === 1 ? 'Active' : 'Inactive'}
                    </div>
                  </div>
                ))}
              </RadioGroup>
            )}
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button
              type="button"
              variant="outline"
              onClick={() => window.location.href = '/'}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || adAccounts.length === 0 || !selectedAccountId}
            >
              {isLoading ? 'Saving...' : 'Continue'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};

export default SelectAdAccount; 