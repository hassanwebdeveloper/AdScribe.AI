import React from 'react';
import SettingsForm from '@/components/settings/SettingsForm';

const Settings: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col p-4 md:p-8">
      <div className="max-w-4xl mx-auto w-full">
        <h1 className="text-3xl font-bold mb-6">Settings</h1>
        <SettingsForm />
      </div>
    </div>
  );
};

export default Settings;
