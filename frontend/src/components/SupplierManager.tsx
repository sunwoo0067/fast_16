import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  Tag,
  message,
  Tooltip,
  Divider
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  LinkOutlined,
  TestTubeOutlined
} from '@ant-design/icons';
import { useSuppliersStore } from '@/stores/suppliers';
import { Supplier, SupplierAccount } from '@/types';

const { Option } = Select;

interface SupplierManagerProps {
  onSupplierSelect?: (supplier: Supplier) => void;
}

const SupplierManager: React.FC<SupplierManagerProps> = ({ onSupplierSelect }) => {
  const {
    suppliers,
    currentSupplier,
    supplierAccounts,
    loading,
    error,
    fetchSuppliers,
    fetchSupplier,
    createSupplier,
    updateSupplier,
    deleteSupplier,
    fetchSupplierAccounts,
    createSupplierAccount,
    testConnection,
    setCurrentSupplier,
    clearError
  } = useSuppliersStore();

  const [supplierModalVisible, setSupplierModalVisible] = useState(false);
  const [accountModalVisible, setAccountModalVisible] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [supplierForm] = Form.useForm();
  const [accountForm] = Form.useForm();
  const [testConnectionModalVisible, setTestConnectionModalVisible] = useState(false);
  const [testConnectionLoading, setTestConnectionLoading] = useState(false);

  useEffect(() => {
    fetchSuppliers();
  }, []);

  const handleCreateSupplier = async (values: any) => {
    try {
      await createSupplier(values);
      message.success('공급사가 생성되었습니다.');
      setSupplierModalVisible(false);
      supplierForm.resetFields();
    } catch (error) {
      message.error('공급사 생성 중 오류가 발생했습니다.');
    }
  };

  const handleUpdateSupplier = async (values: any) => {
    if (!editingSupplier) return;

    try {
      await updateSupplier(editingSupplier.id, values);
      message.success('공급사가 수정되었습니다.');
      setSupplierModalVisible(false);
      setEditingSupplier(null);
      supplierForm.resetFields();
    } catch (error) {
      message.error('공급사 수정 중 오류가 발생했습니다.');
    }
  };

  const handleDeleteSupplier = async (supplier: Supplier) => {
    try {
      await deleteSupplier(supplier.id);
      message.success('공급사가 삭제되었습니다.');
    } catch (error) {
      message.error('공급사 삭제 중 오류가 발생했습니다.');
    }
  };

  const handleCreateAccount = async (values: any) => {
    if (!currentSupplier) return;

    try {
      await createSupplierAccount(currentSupplier.id, values);
      message.success('공급사 계정이 생성되었습니다.');
      setAccountModalVisible(false);
      accountForm.resetFields();
      fetchSupplierAccounts(currentSupplier.id);
    } catch (error) {
      message.error('공급사 계정 생성 중 오류가 발생했습니다.');
    }
  };

  const handleTestConnection = async (values: any) => {
    setTestConnectionLoading(true);
    try {
      await testConnection({
        supplier_id: currentSupplier?.id || 0,
        account_name: values.account_name
      });

      if (!error) {
        message.success('연결 테스트에 성공했습니다.');
        setTestConnectionModalVisible(false);
      }
    } catch (error) {
      message.error('연결 테스트에 실패했습니다.');
    } finally {
      setTestConnectionLoading(false);
    }
  };

  const openEditModal = (supplier: Supplier) => {
    setEditingSupplier(supplier);
    supplierForm.setFieldsValue(supplier);
    setSupplierModalVisible(true);
  };

  const supplierColumns = [
    {
      title: '공급사명',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Supplier) => (
        <Button
          type="link"
          onClick={() => {
            setCurrentSupplier(record);
            fetchSupplierAccounts(record.id);
            onSupplierSelect?.(record);
          }}
        >
          {name}
        </Button>
      ),
    },
    {
      title: '설명',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '상태',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (is_active: boolean) => (
        <Tag color={is_active ? 'green' : 'red'}>
          {is_active ? '활성' : '비활성'}
        </Tag>
      ),
    },
    {
      title: '액션',
      key: 'actions',
      render: (record: Supplier) => (
        <Space>
          <Tooltip title="수정">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => openEditModal(record)}
            />
          </Tooltip>
          <Tooltip title="삭제">
            <Button
              type="text"
              icon={<DeleteOutlined />}
              danger
              onClick={() => {
                Modal.confirm({
                  title: '공급사 삭제',
                  content: `${record.name} 공급사를 삭제하시겠습니까?`,
                  onOk: () => handleDeleteSupplier(record),
                });
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const accountColumns = [
    {
      title: '계정명',
      dataIndex: 'account_name',
      key: 'account_name',
    },
    {
      title: '사용자명',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '상태',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (is_active: boolean) => (
        <Tag color={is_active ? 'green' : 'red'}>
          {is_active ? '활성' : '비활성'}
        </Tag>
      ),
    },
    {
      title: '성공률',
      dataIndex: 'success_rate',
      key: 'success_rate',
      render: (rate: number) => `${(rate * 100).toFixed(1)}%`,
    },
    {
      title: '마지막 사용',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      render: (date: string) => {
        if (!date) return '-';
        return new Date(date).toLocaleString();
      },
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

      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingSupplier(null);
            supplierForm.resetFields();
            setSupplierModalVisible(true);
          }}
        >
          공급사 추가
        </Button>
      </div>

      {/* 공급사 테이블 */}
      <Card title="공급사 목록" style={{ marginBottom: 16 }}>
        <Table
          columns={supplierColumns}
          dataSource={suppliers}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      {/* 선택된 공급사의 계정 목록 */}
      {currentSupplier && (
        <Card
          title={`${currentSupplier.name} - 계정 목록`}
          extra={
            <Space>
              <Button
                icon={<PlusOutlined />}
                onClick={() => setAccountModalVisible(true)}
              >
                계정 추가
              </Button>
              <Button
                icon={<TestTubeOutlined />}
                onClick={() => setTestConnectionModalVisible(true)}
              >
                연결 테스트
              </Button>
            </Space>
          }
        >
          <Table
            columns={accountColumns}
            dataSource={supplierAccounts}
            rowKey="id"
            loading={loading}
            pagination={false}
          />
        </Card>
      )}

      {/* 공급사 생성/수정 모달 */}
      <Modal
        title={editingSupplier ? '공급사 수정' : '공급사 추가'}
        open={supplierModalVisible}
        onCancel={() => {
          setSupplierModalVisible(false);
          setEditingSupplier(null);
          supplierForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={supplierForm}
          layout="vertical"
          onFinish={editingSupplier ? handleUpdateSupplier : handleCreateSupplier}
        >
          <Form.Item
            name="name"
            label="공급사명"
            rules={[{ required: true, message: '공급사명을 입력해주세요' }]}
          >
            <Input placeholder="공급사명을 입력하세요" />
          </Form.Item>

          <Form.Item name="description" label="설명">
            <Input.TextArea placeholder="공급사 설명을 입력하세요" rows={3} />
          </Form.Item>

          <Form.Item name="api_key" label="API 키">
            <Input placeholder="API 키를 입력하세요" />
          </Form.Item>

          <Form.Item name="base_url" label="기본 URL">
            <Input placeholder="API 기본 URL을 입력하세요" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={() => setSupplierModalVisible(false)}>
                취소
              </Button>
              <Button type="primary" htmlType="submit">
                {editingSupplier ? '수정' : '생성'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 공급사 계정 생성 모달 */}
      <Modal
        title="공급사 계정 추가"
        open={accountModalVisible}
        onCancel={() => {
          setAccountModalVisible(false);
          accountForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={accountForm}
          layout="vertical"
          onFinish={handleCreateAccount}
        >
          <Form.Item
            name="account_name"
            label="계정명"
            rules={[{ required: true, message: '계정명을 입력해주세요' }]}
          >
            <Input placeholder="계정명을 입력하세요" />
          </Form.Item>

          <Form.Item
            name="username"
            label="사용자명"
            rules={[{ required: true, message: '사용자명을 입력해주세요' }]}
          >
            <Input placeholder="사용자명을 입력하세요" />
          </Form.Item>

          <Form.Item
            name="password"
            label="비밀번호"
            rules={[{ required: true, message: '비밀번호를 입력해주세요' }]}
          >
            <Input.Password placeholder="비밀번호를 입력하세요" />
          </Form.Item>

          <Form.Item name="default_margin_rate" label="기본 마진율">
            <Input
              type="number"
              step="0.01"
              min="0"
              max="1"
              placeholder="0.3"
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={() => setAccountModalVisible(false)}>
                취소
              </Button>
              <Button type="primary" htmlType="submit">
                계정 생성
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 연결 테스트 모달 */}
      <Modal
        title="연결 테스트"
        open={testConnectionModalVisible}
        onCancel={() => setTestConnectionModalVisible(false)}
        footer={null}
      >
        <Form onFinish={handleTestConnection}>
          <Form.Item
            name="account_name"
            label="테스트할 계정"
            rules={[{ required: true, message: '계정을 선택해주세요' }]}
          >
            <Select placeholder="계정 선택">
              {supplierAccounts.map(account => (
                <Option key={account.id} value={account.account_name}>
                  {account.account_name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={() => setTestConnectionModalVisible(false)}>
                취소
              </Button>
              <Button type="primary" htmlType="submit" loading={testConnectionLoading}>
                연결 테스트
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default SupplierManager;
