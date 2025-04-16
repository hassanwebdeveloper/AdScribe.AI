
import React from 'react';
import SettingsForm from '@/components/settings/SettingsForm';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const Settings: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col p-4 md:p-8">
      <Link to="/chat" className="w-fit mb-8">
        <Button variant="ghost" className="w-fit">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Chat
        </Button>
      </Link>
      
      <div className="max-w-4xl mx-auto w-full">
        <h1 className="text-3xl font-bold mb-6">Settings</h1>
        <SettingsForm />
      </div>
    </div>
  );
};

export default Settings;
