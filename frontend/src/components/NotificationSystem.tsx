import React, { useState, useEffect } from 'react';
import { notification, message, Modal } from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import { useWebSocket } from '@/hooks/useWebSocket';

interface NotificationData {
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
}

const NotificationSystem: React.FC = () => {
  const [api, contextHolder] = notification.useNotification();
  const [messageApi, messageContextHolder] = message.useMessage();

  const { messages } = useWebSocket({
    url: 'ws://localhost:8000/ws/notifications',
    onMessage: (message) => {
      if (message.type === 'notification') {
        showNotification({
          type: message.notification_type || 'info',
          title: message.title,
          message: message.message,
          duration: message.duration || 4.5
        });
      }
    },
  });

  const showNotification = (data: NotificationData) => {
    const { type, title, message, duration = 4.5 } = data;

    switch (type) {
      case 'success':
        api.success({
          message: title,
          description: message,
          duration,
          icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
        });
        break;
      case 'error':
        api.error({
          message: title,
          description: message,
          duration,
          icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
        });
        break;
      case 'warning':
        api.warning({
          message: title,
          description: message,
          duration,
          icon: <ExclamationCircleOutlined style={{ color: '#faad14' }} />,
        });
        break;
      default:
        api.info({
          message: title,
          description: message,
          duration,
          icon: <InfoCircleOutlined style={{ color: '#1890ff' }} />,
        });
    }
  };

  // 전역 에러 처리
  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('Unhandled Promise Rejection:', event.reason);

      api.error({
        message: '예상치 못한 오류',
        description: '시스템에서 처리되지 않은 오류가 발생했습니다.',
        duration: 6,
      });
    };

    const handleError = (event: ErrorEvent) => {
      console.error('Global Error:', event.error);

      api.error({
        message: '시스템 오류',
        description: '예상치 못한 오류가 발생했습니다.',
        duration: 6,
      });
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
    };
  }, [api]);

  return (
    <>
      {contextHolder}
      {messageContextHolder}
    </>
  );
};

// 편의 함수들
export const useNotification = () => {
  const [api, contextHolder] = notification.useNotification();

  const success = (title: string, message: string, duration = 4.5) => {
    api.success({
      message: title,
      description: message,
      duration,
      icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    });
  };

  const error = (title: string, message: string, duration = 6) => {
    api.error({
      message: title,
      description: message,
      duration,
      icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
    });
  };

  const warning = (title: string, message: string, duration = 4.5) => {
    api.warning({
      message: title,
      description: message,
      duration,
      icon: <ExclamationCircleOutlined style={{ color: '#faad14' }} />,
    });
  };

  const info = (title: string, message: string, duration = 4.5) => {
    api.info({
      message: title,
      description: message,
      duration,
      icon: <InfoCircleOutlined style={{ color: '#1890ff' }} />,
    });
  };

  return { api, contextHolder, success, error, warning, info };
};

export const useMessage = () => {
  const [messageApi, messageContextHolder] = message.useMessage();

  const success = (content: string, duration = 3) => {
    messageApi.success(content, duration);
  };

  const error = (content: string, duration = 3) => {
    messageApi.error(content, duration);
  };

  const warning = (content: string, duration = 3) => {
    messageApi.warning(content, duration);
  };

  const info = (content: string, duration = 3) => {
    messageApi.info(content, duration);
  };

  const loading = (content: string, duration = 0) => {
    return messageApi.loading(content, duration);
  };

  return { messageApi, messageContextHolder, success, error, warning, info, loading };
};

export default NotificationSystem;
