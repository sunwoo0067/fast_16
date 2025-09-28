import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Input,
  Select,
  Space,
  Tag,
  Modal,
  Form,
  message,
  Popconfirm,
  Tooltip
} from 'antd';
import {
  SearchOutlined,
  SyncOutlined,
  UploadOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined
} from '@ant-design/icons';
import { useProductsStore } from '@/stores/products';
import { Product, ProductFilters } from '@/types';

const { Option } = Select;

interface ProductListProps {
  onEdit?: (product: Product) => void;
  onView?: (product: Product) => void;
}

const ProductList: React.FC<ProductListProps> = ({ onEdit, onView }) => {
  const {
    products,
    total,
    currentPage,
    pageSize,
    loading,
    error,
    filters,
    fetchProducts,
    syncProducts,
    normalizeProducts,
    publishProducts,
    setFilters,
    setPageSize,
    clearError
  } = useProductsStore();

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [searchForm] = Form.useForm();
  const [syncModalVisible, setSyncModalVisible] = useState(false);
  const [publishModalVisible, setPublishModalVisible] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [publishLoading, setPublishLoading] = useState(false);

  useEffect(() => {
    fetchProducts();
  }, [filters]);

  const handleSearch = (values: any) => {
    setFilters(values);
  };

  const handleTableChange = (pagination: any) => {
    fetchProducts(pagination.current);
  };

  const handleSyncSelected = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('동기화할 상품을 선택해주세요.');
      return;
    }

    setSyncLoading(true);
    try {
      await syncProducts({
        supplier_id: filters.supplier_id || '',
        item_keys: selectedRowKeys as string[]
      });
      message.success('상품 동기화가 시작되었습니다.');
      setSyncModalVisible(false);
    } catch (error) {
      message.error('상품 동기화 중 오류가 발생했습니다.');
    } finally {
      setSyncLoading(false);
    }
  };

  const handlePublishSelected = async (values: any) => {
    if (selectedRowKeys.length === 0) {
      message.warning('업로드할 상품을 선택해주세요.');
      return;
    }

    setPublishLoading(true);
    try {
      await publishProducts(
        values.market_type,
        selectedRowKeys as string[],
        values.account_name
      );
      message.success('상품 업로드가 시작되었습니다.');
      setPublishModalVisible(false);
    } catch (error) {
      message.error('상품 업로드 중 오류가 발생했습니다.');
    } finally {
      setPublishLoading(false);
    }
  };

  const columns = [
    {
      title: '상품명',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string, record: Product) => (
        <Tooltip title={text}>
          <span>{text}</span>
        </Tooltip>
      ),
    },
    {
      title: '브랜드',
      dataIndex: 'brand',
      key: 'brand',
    },
    {
      title: '가격',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => `${price.toLocaleString()}원`,
      sorter: true,
    },
    {
      title: '마진율',
      dataIndex: 'margin_rate',
      key: 'margin_rate',
      render: (rate: number) => `${(rate * 100).toFixed(1)}%`,
    },
    {
      title: '재고',
      dataIndex: 'stock_quantity',
      key: 'stock_quantity',
      render: (quantity: number) => quantity.toLocaleString(),
    },
    {
      title: '동기화 상태',
      dataIndex: 'sync_status',
      key: 'sync_status',
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          'synced': { color: 'green', text: '동기화됨' },
          'pending': { color: 'orange', text: '대기중' },
          'failed': { color: 'red', text: '실패' },
        };
        const statusInfo = statusMap[status] || { color: 'default', text: status };
        return <Tag color={statusInfo.color}>{statusInfo.text}</Tag>;
      },
    },
    {
      title: '마지막 동기화',
      dataIndex: 'last_synced_at',
      key: 'last_synced_at',
      render: (date: string) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
    },
    {
      title: '액션',
      key: 'actions',
      render: (record: Product) => (
        <Space>
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => onView?.(record)}
          >
            보기
          </Button>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => onEdit?.(record)}
          >
            수정
          </Button>
        </Space>
      ),
    },
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
  };

  return (
    <div>
      {/* 에러 메시지 */}
      {error && (
        <div style={{ marginBottom: 16 }}>
          <Alert
            message="오류"
            description={error}
            type="error"
            closable
            onClose={clearError}
          />
        </div>
      )}

      {/* 검색 및 필터 */}
      <Form
        form={searchForm}
        layout="inline"
        onFinish={handleSearch}
        style={{ marginBottom: 16 }}
      >
        <Form.Item name="search">
          <Input
            placeholder="상품명 검색"
            prefix={<SearchOutlined />}
            style={{ width: 200 }}
          />
        </Form.Item>

        <Form.Item name="supplier_id">
          <Select placeholder="공급사" style={{ width: 120 }}>
            <Option value="">전체</Option>
            <Option value="ownerclan">오너클랜</Option>
            <Option value="domeggook">도매꾹</Option>
          </Select>
        </Form.Item>

        <Form.Item name="sync_status">
          <Select placeholder="동기화 상태" style={{ width: 120 }}>
            <Option value="">전체</Option>
            <Option value="synced">동기화됨</Option>
            <Option value="pending">대기중</Option>
            <Option value="failed">실패</Option>
          </Select>
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
            검색
          </Button>
        </Form.Item>
      </Form>

      {/* 액션 버튼들 */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<SyncOutlined />}
            onClick={() => setSyncModalVisible(true)}
            disabled={selectedRowKeys.length === 0}
          >
            선택 상품 동기화 ({selectedRowKeys.length})
          </Button>

          <Button
            icon={<UploadOutlined />}
            onClick={() => setPublishModalVisible(true)}
            disabled={selectedRowKeys.length === 0}
          >
            선택 상품 업로드 ({selectedRowKeys.length})
          </Button>
        </Space>
      </div>

      {/* 상품 테이블 */}
      <Table
        columns={columns}
        dataSource={products}
        rowKey="id"
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize,
          total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) =>
            `${range[0]}-${range[1]} / ${total}개 상품`,
        }}
        rowSelection={rowSelection}
        onChange={handleTableChange}
        scroll={{ x: 1000 }}
      />

      {/* 동기화 모달 */}
      <Modal
        title="상품 동기화"
        open={syncModalVisible}
        onCancel={() => setSyncModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setSyncModalVisible(false)}>
            취소
          </Button>,
          <Button
            key="sync"
            type="primary"
            loading={syncLoading}
            onClick={handleSyncSelected}
          >
            동기화 시작
          </Button>,
        ]}
      >
        <p>선택된 {selectedRowKeys.length}개 상품을 동기화하시겠습니까?</p>
        <p>이 작업은 상품의 최신 정보(가격, 재고 등)를 업데이트합니다.</p>
      </Modal>

      {/* 업로드 모달 */}
      <Modal
        title="상품 업로드"
        open={publishModalVisible}
        onCancel={() => setPublishModalVisible(false)}
        footer={null}
      >
        <Form onFinish={handlePublishSelected}>
          <Form.Item
            name="market_type"
            label="마켓"
            rules={[{ required: true, message: '마켓을 선택해주세요' }]}
          >
            <Select placeholder="마켓 선택">
              <Option value="coupang">쿠팡</Option>
              <Option value="naver">네이버 스마트스토어</Option>
              <Option value="11st">11번가</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="account_name"
            label="계정"
            rules={[{ required: true, message: '계정을 선택해주세요' }]}
          >
            <Select placeholder="계정 선택">
              <Option value="main">메인 계정</Option>
              <Option value="sub">서브 계정</Option>
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={() => setPublishModalVisible(false)}>
                취소
              </Button>
              <Button type="primary" htmlType="submit" loading={publishLoading}>
                업로드 시작
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProductList;
