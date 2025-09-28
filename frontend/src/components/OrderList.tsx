import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Select,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  message,
  Tooltip,
  Divider
} from 'antd';
import {
  EyeOutlined,
  EditOutlined,
  TruckOutlined,
  CloseOutlined,
  DollarOutlined
} from '@ant-design/icons';
import { useOrdersStore } from '@/stores/orders';
import { Order, OrderFilters } from '@/types';

const { Option } = Select;

interface OrderListProps {
  onView?: (order: Order) => void;
  onEdit?: (order: Order) => void;
}

const OrderList: React.FC<OrderListProps> = ({ onView, onEdit }) => {
  const {
    orders,
    total,
    currentPage,
    pageSize,
    loading,
    error,
    filters,
    fetchOrders,
    shipOrder,
    cancelOrder,
    setFilters,
    clearError
  } = useOrdersStore();

  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [shippingModalVisible, setShippingModalVisible] = useState(false);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [shippingForm] = Form.useForm();
  const [cancelForm] = Form.useForm();
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    fetchOrders();
  }, [filters]);

  const handleFilterChange = (key: keyof OrderFilters, value: any) => {
    setFilters({ [key]: value });
  };

  const handleShipping = async (values: any) => {
    if (!selectedOrder) return;

    setActionLoading(true);
    try {
      await shipOrder(
        selectedOrder.id,
        values.tracking_number,
        values.shipping_company
      );
      message.success('배송 정보가 업데이트되었습니다.');
      setShippingModalVisible(false);
      shippingForm.resetFields();
    } catch (error) {
      message.error('배송 정보 업데이트 중 오류가 발생했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async (values: any) => {
    if (!selectedOrder) return;

    setActionLoading(true);
    try {
      await cancelOrder(selectedOrder.id, values.reason);
      message.success('주문이 취소되었습니다.');
      setCancelModalVisible(false);
      cancelForm.resetFields();
    } catch (error) {
      message.error('주문 취소 중 오류가 발생했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      'pending': 'orange',
      'confirmed': 'blue',
      'processing': 'purple',
      'shipped': 'green',
      'delivered': 'green',
      'cancelled': 'red',
    };
    return statusMap[status] || 'default';
  };

  const getPaymentStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      'pending': 'orange',
      'paid': 'green',
      'failed': 'red',
      'refunded': 'blue',
    };
    return statusMap[status] || 'default';
  };

  const columns = [
    {
      title: '주문번호',
      dataIndex: 'order_key',
      key: 'order_key',
      width: 150,
    },
    {
      title: '주문일시',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
      width: 180,
    },
    {
      title: '상품 개수',
      key: 'item_count',
      render: (record: Order) => record.items.length,
      width: 100,
    },
    {
      title: '총 금액',
      dataIndex: 'total_amount',
      key: 'total_amount',
      render: (amount: number) => `${amount.toLocaleString()}원`,
      width: 120,
    },
    {
      title: '주문 상태',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {status.toUpperCase()}
        </Tag>
      ),
      width: 120,
    },
    {
      title: '결제 상태',
      dataIndex: 'payment_status',
      key: 'payment_status',
      render: (status: string) => (
        <Tag color={getPaymentStatusColor(status)}>
          {status.toUpperCase()}
        </Tag>
      ),
      width: 120,
    },
    {
      title: '배송 정보',
      key: 'shipping',
      render: (record: Order) => {
        if (record.shipping_info.tracking_number) {
          return (
            <div>
              <div>{record.shipping_info.shipping_company}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                {record.shipping_info.tracking_number}
              </div>
            </div>
          );
        }
        return '-';
      },
      width: 150,
    },
    {
      title: '액션',
      key: 'actions',
      render: (record: Order) => (
        <Space>
          <Tooltip title="주문 상세">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => onView?.(record)}
            />
          </Tooltip>

          {record.status === 'confirmed' && (
            <Tooltip title="배송 처리">
              <Button
                type="text"
                icon={<TruckOutlined />}
                onClick={() => {
                  setSelectedOrder(record);
                  setShippingModalVisible(true);
                }}
              />
            </Tooltip>
          )}

          {(record.status === 'pending' || record.status === 'confirmed') && (
            <Tooltip title="주문 취소">
              <Button
                type="text"
                icon={<CloseOutlined />}
                danger
                onClick={() => {
                  setSelectedOrder(record);
                  setCancelModalVisible(true);
                }}
              />
            </Tooltip>
          )}
        </Space>
      ),
      width: 150,
    },
  ];

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

      {/* 필터 */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Select
            placeholder="주문 상태"
            style={{ width: 150 }}
            value={filters.status}
            onChange={(value) => handleFilterChange('status', value)}
            allowClear
          >
            <Option value="pending">대기중</Option>
            <Option value="confirmed">확인됨</Option>
            <Option value="processing">처리중</Option>
            <Option value="shipped">발송됨</Option>
            <Option value="delivered">배송완료</Option>
            <Option value="cancelled">취소됨</Option>
          </Select>

          <Select
            placeholder="결제 상태"
            style={{ width: 150 }}
            value={filters.payment_status}
            onChange={(value) => handleFilterChange('payment_status', value)}
            allowClear
          >
            <Option value="pending">대기중</Option>
            <Option value="paid">결제완료</Option>
            <Option value="failed">결제실패</Option>
            <Option value="refunded">환불됨</Option>
          </Select>

          <Button type="primary" onClick={() => fetchOrders(1)}>
            새로고침
          </Button>
        </Space>
      </div>

      {/* 주문 테이블 */}
      <Table
        columns={columns}
        dataSource={orders}
        rowKey="id"
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize,
          total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) =>
            `${range[0]}-${range[1]} / ${total}개 주문`,
        }}
        onChange={(pagination) => fetchOrders(pagination.current)}
        scroll={{ x: 1000 }}
      />

      {/* 배송 정보 입력 모달 */}
      <Modal
        title="배송 정보 입력"
        open={shippingModalVisible}
        onCancel={() => {
          setShippingModalVisible(false);
          shippingForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={shippingForm}
          layout="vertical"
          onFinish={handleShipping}
        >
          <Form.Item
            name="shipping_company"
            label="택배사"
            rules={[{ required: true, message: '택배사를 선택해주세요' }]}
          >
            <Select placeholder="택배사 선택">
              <Option value="cj">CJ대한통운</Option>
              <Option value="hanjin">한진택배</Option>
              <Option value="lotte">롯데택배</Option>
              <Option value="kg">KG로지스</Option>
              <Option value="epost">우체국택배</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="tracking_number"
            label="운송장 번호"
            rules={[{ required: true, message: '운송장 번호를 입력해주세요' }]}
          >
            <Input placeholder="운송장 번호 입력" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={() => setShippingModalVisible(false)}>
                취소
              </Button>
              <Button type="primary" htmlType="submit" loading={actionLoading}>
                배송 처리
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 주문 취소 모달 */}
      <Modal
        title="주문 취소"
        open={cancelModalVisible}
        onCancel={() => {
          setCancelModalVisible(false);
          cancelForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={cancelForm}
          layout="vertical"
          onFinish={handleCancel}
        >
          <Form.Item
            name="reason"
            label="취소 사유"
            rules={[{ required: true, message: '취소 사유를 입력해주세요' }]}
          >
            <Input.TextArea
              placeholder="취소 사유를 입력해주세요"
              rows={3}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={() => setCancelModalVisible(false)}>
                취소
              </Button>
              <Button type="primary" danger htmlType="submit" loading={actionLoading}>
                주문 취소
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default OrderList;
