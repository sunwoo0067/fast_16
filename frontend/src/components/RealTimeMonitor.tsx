import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Progress, Alert, Badge, List } from 'antd';
import {
  WifiOutlined,
  DisconnectOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDashboardStore } from '@/stores/dashboard';

interface SyncStatus {
  active_syncs: number;
  completed_syncs: number;
  failed_syncs: number;
  total_products: number;
  total_orders: number;
}

interface Notification {
  type: string;
  timestamp: string;
  title: string;
  message: string;
  notification_type: 'info' | 'success' | 'warning' | 'error';
}

const RealTimeMonitor: React.FC = () => {
  const { stats, fetchStats } = useDashboardStore();
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({
    active_syncs: 0,
    completed_syncs: 0,
    failed_syncs: 0,
    total_products: 0,
    total_orders: 0
  });
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // WebSocket 연결
  const { isConnected, messages } = useWebSocket({
    url: 'ws://localhost:8000/ws/sync-status',
    onMessage: (message) => {
      if (message.type === 'sync_status') {
        setSyncStatus(message.data);
      }
    },
  });

  const { isConnected: notificationConnected } = useWebSocket({
    url: 'ws://localhost:8000/ws/notifications',
    onMessage: (message) => {
      if (message.type === 'notification') {
        const notification: Notification = {
          type: message.type,
          timestamp: message.timestamp,
          title: message.title,
          message: message.message,
          notification_type: message.notification_type || 'info'
        };
        setNotifications(prev => [notification, ...prev.slice(0, 9)]); // 최근 10개만 유지
      }
    },
  });

  useEffect(() => {
    // 30초마다 통계 새로고침
    const interval = setInterval(() => {
      fetchStats();
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchStats]);

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'warning':
        return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <ClockCircleOutlined style={{ color: '#1890ff' }} />;
    }
  };

  const getNotificationColor = (type: string) => {
    switch (type) {
      case 'success':
        return '#f6ffed';
      case 'warning':
        return '#fffbe6';
      case 'error':
        return '#fff2e8';
      default:
        return '#e6f7ff';
    }
  };

  return (
    <div>
      {/* 연결 상태 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card size="small">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {isConnected ? (
                <WifiOutlined style={{ color: '#52c41a' }} />
              ) : (
                <DisconnectOutlined style={{ color: '#ff4d4f' }} />
              )}
              <span>동기화 상태: {isConnected ? '연결됨' : '연결 끊김'}</span>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {notificationConnected ? (
                <WifiOutlined style={{ color: '#52c41a' }} />
              ) : (
                <DisconnectOutlined style={{ color: '#ff4d4f' }} />
              )}
              <span>알림: {notificationConnected ? '연결됨' : '연결 끊김'}</span>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 실시간 통계 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="활성 동기화"
              value={syncStatus.active_syncs}
              prefix={<SyncOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="완료된 동기화"
              value={syncStatus.completed_syncs}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="실패한 동기화"
              value={syncStatus.failed_syncs}
              prefix={<ExclamationCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="총 상품"
              value={syncStatus.total_products}
              prefix={<SyncOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 동기화 진행률 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card title="동기화 진행률">
            <div style={{ padding: '20px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <Progress
                  type="circle"
                  percent={Math.min(100, Math.round((syncStatus.completed_syncs / Math.max(syncStatus.active_syncs + syncStatus.completed_syncs, 1)) * 100))}
                  width={80}
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#87d068',
                  }}
                />
                <div>
                  <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
                    {syncStatus.completed_syncs} / {syncStatus.active_syncs + syncStatus.completed_syncs}
                  </div>
                  <div style={{ color: '#666' }}>
                    완료된 동기화 작업
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 실시간 알림 */}
      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="실시간 알림" style={{ height: '400px' }}>
            <List
              dataSource={notifications.slice(0, 5)}
              renderItem={(notification) => (
                <List.Item>
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    padding: '12px',
                    background: getNotificationColor(notification.notification_type),
                    borderRadius: '6px',
                    width: '100%'
                  }}>
                    {getNotificationIcon(notification.notification_type)}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                        {notification.title}
                      </div>
                      <div style={{ fontSize: '14px', color: '#666' }}>
                        {notification.message}
                      </div>
                      <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
                        {new Date(notification.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </List.Item>
              )}
              locale={{ emptyText: '알림이 없습니다.' }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="시스템 상태" style={{ height: '400px' }}>
            <div style={{ padding: '20px 0' }}>
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="총 상품"
                    value={stats?.total_products || 0}
                    prefix={<SyncOutlined />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="동기화된 상품"
                    value={stats?.sync_products || 0}
                    prefix={<CheckCircleOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
              </Row>

              <div style={{ margin: '24px 0' }}>
                <div style={{ marginBottom: '8px' }}>동기화 성공률</div>
                <Progress
                  percent={stats?.sync_products && stats?.total_products ?
                    Math.round((stats.sync_products / stats.total_products) * 100) : 0}
                  status={stats?.sync_products === stats?.total_products ? 'success' : 'active'}
                />
              </div>

              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="총 주문"
                    value={stats?.total_orders || 0}
                    prefix={<SyncOutlined />}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="평균 주문가"
                    value={stats?.average_order_value || 0}
                    prefix={<CheckCircleOutlined />}
                    formatter={(value) => `${value.toLocaleString()}원`}
                  />
                </Col>
              </Row>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default RealTimeMonitor;
