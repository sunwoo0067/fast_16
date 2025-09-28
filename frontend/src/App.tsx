import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout, Menu, Breadcrumb } from 'antd';
import {
  DashboardOutlined,
  ShoppingOutlined,
  ShoppingCartOutlined,
  SettingOutlined,
  SyncOutlined
} from '@ant-design/icons';
import ErrorBoundary from '@/components/ErrorBoundary';
import NotificationSystem from '@/components/NotificationSystem';
import Dashboard from '@/components/Dashboard';
import ProductList from '@/components/ProductList';
import OrderList from '@/components/OrderList';
import SupplierManager from '@/components/SupplierManager';
import RealTimeMonitor from '@/components/RealTimeMonitor';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => {
  const [collapsed, setCollapsed] = React.useState(false);

  const menuItems = [
    {
      key: 'dashboard',
      icon: <DashboardOutlined />,
      label: '대시보드',
    },
    {
      key: 'products',
      icon: <ShoppingOutlined />,
      label: '상품 관리',
    },
    {
      key: 'orders',
      icon: <ShoppingCartOutlined />,
      label: '주문 관리',
    },
    {
      key: 'suppliers',
      icon: <SettingOutlined />,
      label: '공급사 관리',
    },
    {
      key: 'monitor',
      icon: <SyncOutlined />,
      label: '실시간 모니터링',
    },
    {
      key: 'sync',
      icon: <SyncOutlined />,
      label: '동기화 관리',
    },
  ];

  return (
    <ErrorBoundary>
      <NotificationSystem />
      <Router>
        <Layout style={{ minHeight: '100vh' }}>
          <Sider
            collapsible
            collapsed={collapsed}
            onCollapse={setCollapsed}
            theme="dark"
          >
            <div style={{
              height: '32px',
              margin: '16px',
              background: 'rgba(255, 255, 255, 0.2)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <span style={{ color: 'white', fontSize: collapsed ? '12px' : '16px' }}>
                {collapsed ? 'DS' : '드랍십핑'}
              </span>
            </div>

            <Menu
              theme="dark"
              defaultSelectedKeys={['dashboard']}
              mode="inline"
              items={menuItems}
            />
          </Sider>

          <Layout>
            <Header style={{
              background: '#fff',
              padding: '0 24px',
              borderBottom: '1px solid #f0f0f0'
            }}>
              <Breadcrumb style={{ margin: '16px 0' }}>
                <Breadcrumb.Item>드랍십핑 자동화</Breadcrumb.Item>
                <Breadcrumb.Item>관리자</Breadcrumb.Item>
              </Breadcrumb>
            </Header>

            <Content style={{ margin: '24px 16px', padding: 24, background: '#fff' }}>
              <Routes>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/products" element={<ProductList />} />
                <Route path="/orders" element={<OrderList />} />
                <Route path="/suppliers" element={<SupplierManager />} />
                <Route path="/monitor" element={<RealTimeMonitor />} />
                <Route path="/sync" element={<div>동기화 관리 페이지 (준비중)</div>} />
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Content>
          </Layout>
        </Layout>
      </Router>
    </ErrorBoundary>
  );
};

export default App;
