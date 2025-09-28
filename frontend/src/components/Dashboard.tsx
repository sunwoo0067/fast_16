import React, { useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Spin, Alert } from 'antd';
import { ShoppingCartOutlined, ProductOutlined, SyncOutlined, DollarOutlined } from '@ant-design/icons';
import { useDashboardStore } from '@/stores/dashboard';
import { Product, Order, SyncHistory } from '@/types';

const Dashboard: React.FC = () => {
  const {
    stats,
    recentProducts,
    recentOrders,
    recentSyncs,
    loading,
    error,
    fetchStats,
    fetchRecentProducts,
    fetchRecentOrders,
    fetchRecentSyncs,
    clearError
  } = useDashboardStore();

  useEffect(() => {
    // 컴포넌트 마운트 시 데이터 로드
    fetchStats();
    fetchRecentProducts();
    fetchRecentOrders();
    fetchRecentSyncs();

    // 5분마다 데이터 새로고침
    const interval = setInterval(() => {
      fetchStats();
      fetchRecentProducts();
      fetchRecentOrders();
      fetchRecentSyncs();
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const productColumns = [
    {
      title: '상품명',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '가격',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => `${price.toLocaleString()}원`,
    },
    {
      title: '상태',
      dataIndex: 'sync_status',
      key: 'sync_status',
      render: (status: string) => {
        const statusMap: Record<string, { text: string; type: 'success' | 'warning' | 'danger' }> = {
          'synced': { text: '동기화됨', type: 'success' },
          'pending': { text: '대기중', type: 'warning' },
          'failed': { text: '실패', type: 'danger' },
        };
        const statusInfo = statusMap[status] || { text: status, type: 'warning' };
        return <span style={{ color: statusInfo.type === 'success' ? '#52c41a' : statusInfo.type === 'danger' ? '#ff4d4f' : '#faad14' }}>{statusInfo.text}</span>;
      },
    },
  ];

  const orderColumns = [
    {
      title: '주문번호',
      dataIndex: 'order_key',
      key: 'order_key',
    },
    {
      title: '총 금액',
      dataIndex: 'total_amount',
      key: 'total_amount',
      render: (amount: number) => `${amount.toLocaleString()}원`,
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, { text: string; color: string }> = {
          'pending': { text: '대기중', color: '#faad14' },
          'confirmed': { text: '확인됨', color: '#1890ff' },
          'processing': { text: '처리중', color: '#722ed1' },
          'shipped': { text: '발송됨', color: '#52c41a' },
          'delivered': { text: '배송완료', color: '#52c41a' },
          'cancelled': { text: '취소됨', color: '#ff4d4f' },
        };
        const statusInfo = statusMap[status] || { text: status, color: '#d9d9d9' };
        return <span style={{ color: statusInfo.color }}>{statusInfo.text}</span>;
      },
    },
  ];

  const syncColumns = [
    {
      title: '동기화 타입',
      dataIndex: 'sync_type',
      key: 'sync_type',
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, { text: string; color: string }> = {
          'success': { text: '성공', color: '#52c41a' },
          'failed': { text: '실패', color: '#ff4d4f' },
          'pending': { text: '대기중', color: '#faad14' },
          'in_progress': { text: '진행중', color: '#1890ff' },
        };
        const statusInfo = statusMap[status] || { text: status, color: '#d9d9d9' };
        return <span style={{ color: statusInfo.color }}>{statusInfo.text}</span>;
      },
    },
    {
      title: '성공률',
      key: 'success_rate',
      render: (record: SyncHistory) => {
        if (record.result) {
          return `${(record.result.success_rate * 100).toFixed(1)}%`;
        }
        return '-';
      },
    },
    {
      title: '실행 시간',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (started_at: string) => {
        if (started_at) {
          return new Date(started_at).toLocaleString();
        }
        return '-';
      },
    },
  ];

  if (error) {
    return (
      <Alert
        message="오류"
        description={error}
        type="error"
        closable
        onClose={clearError}
        style={{ marginBottom: 16 }}
      />
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '24px', marginBottom: '24px', fontWeight: 'bold' }}>
        드랍십핑 자동화 대시보드
      </h1>

      {/* 통계 카드 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="총 상품"
              value={stats?.total_products || 0}
              prefix={<ProductOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="총 주문"
              value={stats?.total_orders || 0}
              prefix={<ShoppingCartOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="동기화 완료"
              value={stats?.sync_products || 0}
              prefix={<SyncOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="총 매출"
              value={stats?.total_revenue || 0}
              prefix={<DollarOutlined />}
              valueStyle={{ color: '#fa8c16' }}
              formatter={(value) => `${value.toLocaleString()}원`}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 최근 상품 */}
        <Col xs={24} lg={8}>
          <Card
            title="최근 동기화된 상품"
            extra={<a href="/products">더보기</a>}
            style={{ height: '400px' }}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: '50px 0' }}>
                <Spin size="large" />
              </div>
            ) : (
              <Table
                columns={productColumns}
                dataSource={recentProducts.slice(0, 5)}
                pagination={false}
                size="small"
                rowKey="id"
                scroll={{ y: 280 }}
              />
            )}
          </Card>
        </Col>

        {/* 최근 주문 */}
        <Col xs={24} lg={8}>
          <Card
            title="최근 주문"
            extra={<a href="/orders">더보기</a>}
            style={{ height: '400px' }}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: '50px 0' }}>
                <Spin size="large" />
              </div>
            ) : (
              <Table
                columns={orderColumns}
                dataSource={recentOrders.slice(0, 5)}
                pagination={false}
                size="small"
                rowKey="id"
                scroll={{ y: 280 }}
              />
            )}
          </Card>
        </Col>

        {/* 최근 동기화 */}
        <Col xs={24} lg={8}>
          <Card
            title="최근 동기화 작업"
            extra={<a href="/sync-history">더보기</a>}
            style={{ height: '400px' }}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: '50px 0' }}>
                <Spin size="large" />
              </div>
            ) : (
              <Table
                columns={syncColumns}
                dataSource={recentSyncs.slice(0, 5)}
                pagination={false}
                size="small"
                rowKey="id"
                scroll={{ y: 280 }}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
