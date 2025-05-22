import React, { useState, useEffect } from 'react';
import { Button, Card, Typography, Space, message } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

const { Title } = Typography;

interface CollectionStatus {
  status: boolean;
  is_running: boolean;
}

const AdAnalysis: React.FC = () => {
  const { user } = useAuth();
  const [isCollecting, setIsCollecting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchCollectionStatus();
  }, []);

  const fetchCollectionStatus = async () => {
    try {
      console.log('Fetching collection status...');
      const response = await api.get<CollectionStatus>('/ad-analysis/collection-status');
      console.log('Collection status response:', response.data);
      
      // Use only the database status, not the job running status
      const newStatus = response.data.status;
      console.log('Setting collection status to:', newStatus);
      setIsCollecting(newStatus);
    } catch (error) {
      console.error('Error fetching collection status:', error);
      message.error('Failed to fetch collection status');
    }
  };

  const handleToggleCollection = async () => {
    try {
      setIsLoading(true);
      console.log('Toggling collection...');
      const response = await api.post<{ status: boolean }>('/ad-analysis/toggle-collection');
      console.log('Toggle response:', response.data);
      
      // Update state based on response
      setIsCollecting(response.data.status);
      message.success(response.data.status ? 'Data collection started' : 'Data collection stopped');
      
      // Refresh status after a short delay to ensure it's in sync
      setTimeout(() => {
        fetchCollectionStatus();
      }, 1000);
    } catch (error) {
      console.error('Error toggling collection:', error);
      message.error('Failed to toggle data collection');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Title level={4}>Ad Analysis</Title>
        
        <Space>
          <Button
            type="primary"
            icon={isCollecting ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={handleToggleCollection}
            loading={isLoading}
          >
            {isCollecting ? 'Stop Data Collection' : 'Start Data Collection'}
          </Button>
        </Space>
      </Space>
    </Card>
  );
};

export default AdAnalysis; 