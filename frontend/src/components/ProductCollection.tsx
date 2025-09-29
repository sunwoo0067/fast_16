import React, { useState, useEffect } from 'react';
import { Card, Button, Table, Space, message, Select, Input, DatePicker, Row, Col, Statistic, Radio } from 'antd';
import { CloudDownloadOutlined, SyncOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { useSuppliersStore } from '@/stores/suppliers';
import { apiClient } from '@/services/api';
import ProgressTrackerPolling from './ProgressTrackerPolling';

const { Option } = Select;
const { RangePicker } = DatePicker;

interface CollectionStats {
  total_collected: number;
  success_count: number;
  failed_count: number;
  last_collection: string;
}

const ProductCollection: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<CollectionStats>({
    total_collected: 0,
    success_count: 0,
    failed_count: 0,
    last_collection: ''
  });
  const [selectedSupplier, setSelectedSupplier] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<string>('all');
  const [collectionHistory, setCollectionHistory] = useState<any[]>([]);
  const [currentTaskId, setCurrentTaskId] = useState<string | undefined>();

  const { suppliers, fetchSuppliers } = useSuppliersStore();

  const dateFilterOptions = [
    { value: 'all', label: '전체' },
    { value: '1', label: '최근 1일' },
    { value: '3', label: '최근 3일' },
    { value: '7', label: '최근 7일' },
    { value: '14', label: '최근 14일' },
    { value: '30', label: '최근 30일' }
  ];

  useEffect(() => {
    fetchSuppliers();
    fetchCollectionStats();
    fetchCollectionHistory();
  }, [fetchSuppliers]);

  const fetchCollectionStats = async () => {
    try {
      // 실제 API 호출로 통계 조회
      const response = await apiClient.get('/products/stats');
      setStats({
        total_collected: response.data.total_collected || 0,
        success_count: response.data.success_count || 0,
        failed_count: response.data.failed_count || 0,
        last_collection: response.data.last_collection || ''
      });
    } catch (error) {
      console.error('통계 조회 실패:', error);
      // API 호출 실패 시 기본값 설정
      setStats({
        total_collected: 0,
        success_count: 0,
        failed_count: 0,
        last_collection: ''
      });
    }
  };

  const fetchCollectionHistory = async () => {
    try {
      // 실제 API 호출로 수집 이력 조회
      const response = await apiClient.get('/products/collection-history');
      setCollectionHistory(response.data.history || []);
    } catch (error) {
      console.error('수집 이력 조회 실패:', error);
      setCollectionHistory([]);
    }
  };

  const handleCollection = async () => {
    if (!selectedSupplier) {
      message.warning('공급사를 선택해주세요.');
      return;
    }

    setLoading(true);
    try {
      const supplierName = selectedSupplier === 'all' ? '전체 공급사' : selectedSupplier;
      
              if (selectedSupplier === 'OwnerClan' || selectedSupplier === 'all') {
                // OwnerClan API 직접 호출
                const response = await fetch('/api/v1/ownerclan/collect-products', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    supplier_id: 1,
                    supplier_account_id: 1,
                    count: 10
                  })
                });
                
                if (!response.ok) {
                  throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                message.success(`${supplierName} 상품 수집 완료: ${data.data.collected}개 수집`);
              } else {
                // 새로운 진행 상황 추적 API 사용
                const response = await fetch('/api/v1/products/collect', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({
                    supplier_id: parseInt(selectedSupplier),
                    supplier_account_id: null,
                    force_sync: false
                  })
                });
                
                if (!response.ok) {
                  throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                setCurrentTaskId(data.task_id);
                message.success(`${supplierName} 상품 수집이 시작되었습니다. (작업 ID: ${data.task_id})`);
              }
      
      fetchCollectionStats();
      fetchCollectionHistory();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '상품 수집 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '공급사',
      dataIndex: 'supplier',
      key: 'supplier',
    },
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <span style={{ color: status === 'success' ? 'green' : 'red' }}>
          {status === 'success' ? '성공' : '실패'}
        </span>
      ),
    },
    {
      title: '수집 수량',
      dataIndex: 'collected_count',
      key: 'collected_count',
    },
    {
      title: '수집 시간',
      dataIndex: 'timestamp',
      key: 'timestamp',
    },
  ];

  const handleTaskComplete = (taskId: string, result: any) => {
    message.success('상품 수집이 완료되었습니다!');
    setCurrentTaskId(undefined);
    fetchCollectionStats();
    fetchCollectionHistory();
  };

  const handleTaskError = (taskId: string, error: string) => {
    message.error(`상품 수집 중 오류가 발생했습니다: ${error}`);
    setCurrentTaskId(undefined);
    fetchCollectionStats();
    fetchCollectionHistory();
  };

  return (
    <div>
      {/* 실시간 진행 상황 추적 */}
      <ProgressTrackerPolling 
        taskId={currentTaskId}
        onTaskComplete={handleTaskComplete}
        onTaskError={handleTaskError}
      />
      
      <Card style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, marginBottom: 16 }}>
          <CloudDownloadOutlined /> 상품수집
        </h2>
        <p>공급사로부터 상품 데이터를 수집합니다.</p>
        
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={6}>
            <Statistic title="총 수집 상품" value={stats.total_collected} />
          </Col>
          <Col xs={24} sm={6}>
            <Statistic title="성공" value={stats.success_count} valueStyle={{ color: 'green' }} />
          </Col>
          <Col xs={24} sm={6}>
            <Statistic title="실패" value={stats.failed_count} valueStyle={{ color: 'red' }} />
          </Col>
          <Col xs={24} sm={6}>
            <Statistic title="마지막 수집" value={stats.last_collection} />
          </Col>
        </Row>

        <Row gutter={16} align="middle">
          <Col xs={24} sm={6}>
            <Select
              style={{ width: '100%' }}
              placeholder="공급사 선택"
              value={selectedSupplier}
              onChange={setSelectedSupplier}
            >
              <Option key="all" value="all">
                <strong>전체 공급사</strong>
              </Option>
              {suppliers.map(supplier => (
                <Option key={supplier.id} value={supplier.id.toString()}>
                  {supplier.name}
                </Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} sm={6}>
            <Select
              style={{ width: '100%' }}
              placeholder="날짜 필터"
              value={dateFilter}
              onChange={setDateFilter}
            >
              {dateFilterOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  {option.label}
                </Option>
              ))}
            </Select>
          </Col>
          <Col xs={24} sm={12}>
            <Space>
              <Button
                type="primary"
                icon={<SyncOutlined />}
                loading={loading}
                onClick={handleCollection}
                disabled={!selectedSupplier}
              >
                상품 수집 시작
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  fetchCollectionStats();
                  fetchCollectionHistory();
                }}
              >
                새로고침
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card title="수집 이력">
        <Table
          columns={columns}
          dataSource={collectionHistory}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
};

export default ProductCollection;
