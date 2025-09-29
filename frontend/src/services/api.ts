import axios, { AxiosInstance, AxiosResponse } from 'axios';
import {
  Product,
  ProductListResponse,
  Order,
  OrderListResponse,
  Supplier,
  SupplierAccount,
  SyncHistory,
  DashboardStats,
  ProductFilters,
  OrderFilters,
  ProductSyncRequest,
  ProductSyncResponse,
  OrderCreateRequest,
  SupplierTestRequest,
  ApiResponse
} from '@/types';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: '/api/v1',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 응답 인터셉터
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error) => {
        if (error.response?.status === 401) {
          // 인증 오류 처리
          console.error('인증이 필요합니다.');
        } else if (error.response?.status >= 500) {
          console.error('서버 오류가 발생했습니다.');
        }
        return Promise.reject(error);
      }
    );
  }

  // 헬스체크
  async healthCheck(): Promise<ApiResponse> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // 상품 관련 API
  async getProducts(filters: ProductFilters = {}): Promise<ProductListResponse> {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, value.toString());
      }
    });

    const response = await this.client.get(`/products?${params}`);
    return response.data;
  }

  async getProduct(productId: string): Promise<Product> {
    const response = await this.client.get(`/products/${productId}`);
    return response.data;
  }

  async syncProducts(request: ProductSyncRequest): Promise<ProductSyncResponse> {
    const response = await this.client.post('/products/collect', request);
    return response.data;
  }

  async normalizeProducts(request: { supplier_id?: string; item_ids?: string[] }): Promise<ApiResponse> {
    const response = await this.client.post('/products/normalize', request);
    return response.data;
  }

  async publishProducts(request: {
    market_type: string;
    item_ids: string[];
    account_name: string;
    dry_run?: boolean;
  }): Promise<ApiResponse> {
    const response = await this.client.post('/products/publish', request);
    return response.data;
  }

  // 주문 관련 API
  async getOrders(filters: OrderFilters = {}): Promise<OrderListResponse> {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, value.toString());
      }
    });

    const response = await this.client.get(`/orders?${params}`);
    return response.data;
  }

  async getOrder(orderId: string): Promise<Order> {
    const response = await this.client.get(`/orders/${orderId}`);
    return response.data;
  }

  async createOrder(orderData: OrderCreateRequest): Promise<Order> {
    const response = await this.client.post('/orders', orderData);
    return response.data;
  }

  async updateOrderStatus(orderId: string, status: string, reason?: string): Promise<Order> {
    const response = await this.client.put(`/orders/${orderId}`, {
      status,
      reason
    });
    return response.data;
  }

  async shipOrder(orderId: string, trackingNumber: string, shippingCompany: string): Promise<Order> {
    const response = await this.client.post(`/orders/${orderId}/ship`, {
      tracking_number: trackingNumber,
      shipping_company: shippingCompany
    });
    return response.data;
  }

  async cancelOrder(orderId: string, reason: string): Promise<Order> {
    const response = await this.client.post(`/orders/${orderId}/cancel`, {
      reason
    });
    return response.data;
  }

  // 공급사 관련 API
  async getSuppliers(): Promise<Supplier[]> {
    const response = await this.client.get('/suppliers');
    return response.data;
  }

  async getSupplier(supplierId: number): Promise<Supplier> {
    const response = await this.client.get(`/suppliers/${supplierId}`);
    return response.data;
  }

  async createSupplier(supplierData: Partial<Supplier>): Promise<Supplier> {
    const response = await this.client.post('/suppliers', supplierData);
    return response.data;
  }

  async updateSupplier(supplierId: number, supplierData: Partial<Supplier>): Promise<Supplier> {
    const response = await this.client.put(`/suppliers/${supplierId}`, supplierData);
    return response.data;
  }

  async deleteSupplier(supplierId: number): Promise<void> {
    await this.client.delete(`/suppliers/${supplierId}`);
  }

  async getSupplierAccounts(supplierId: number): Promise<SupplierAccount[]> {
    const response = await this.client.get(`/suppliers/${supplierId}/accounts`);
    return response.data.accounts;
  }

  async createSupplierAccount(supplierId: number, accountData: Partial<SupplierAccount>): Promise<SupplierAccount> {
    const response = await this.client.post(`/suppliers/${supplierId}/accounts`, accountData);
    return response.data;
  }

  async updateSupplierAccount(supplierId: number, accountId: number, accountData: Partial<SupplierAccount>): Promise<SupplierAccount> {
    const response = await this.client.put(`/suppliers/${supplierId}/accounts/${accountId}`, accountData);
    return response.data;
  }

  async testSupplierConnection(request: SupplierTestRequest): Promise<ApiResponse> {
    const response = await this.client.post('/suppliers/test-connection', request);
    return response.data;
  }

  // 동기화 관련 API
  async collectOrders(orders: any[]): Promise<ApiResponse> {
    const response = await this.client.post('/order-collection/collect', orders);
    return response.data;
  }

  async getSyncHistory(filters: {
    item_id?: string;
    supplier_id?: string;
    sync_type?: string;
    limit?: number;
  } = {}): Promise<SyncHistory[]> {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, value.toString());
      }
    });

    const response = await this.client.get(`/dashboard/sync-history?${params}`);
    return response.data;
  }

  // 통계 관련 API
  async getDashboardStats(): Promise<DashboardStats> {
    const response = await this.client.get('/dashboard/stats');
    return response.data;
  }

  // 동기화 관련 API
  async getSyncHistory(filters: any = {}): Promise<any> {
    const params = new URLSearchParams();

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, value.toString());
      }
    });

    const response = await this.client.get(`/dashboard/sync-history?${params}`);
    return response.data;
  }

  async getSyncStats(): Promise<any> {
    const response = await this.client.get('/dashboard/sync-history/stats');
    return response.data;
  }

  async retrySync(recordId: string): Promise<any> {
    const response = await this.client.post(`/dashboard/sync-history/${recordId}/retry`);
    return response.data;
  }

  async cancelSync(recordId: string): Promise<any> {
    const response = await this.client.post(`/dashboard/sync-history/${recordId}/cancel`);
    return response.data;
  }

  // 공급사 동기화 관련 API
  async syncSupplierProducts(supplierId: string, accountId?: string, dateFilter?: string): Promise<any> {
    const requestData: any = {
      supplier_id: supplierId,
      account_id: accountId
    };

    // 날짜 필터가 있고 'all'이 아닌 경우 추가
    if (dateFilter && dateFilter !== 'all') {
      requestData.date_filter = dateFilter;
    }

    const response = await this.client.post('/products/collect', requestData);
    return response.data;
  }

  async syncAllSuppliers(): Promise<any> {
    const response = await this.client.post('/products/collect/all');
    return response.data;
  }

  // OwnerClan API
  async collectOwnerClanProducts(request: {
    supplier_id: number;
    supplier_account_id: number;
    count: number;
  }): Promise<any> {
    const response = await this.client.post('/ownerclan/collect-products', request);
    return response.data;
  }

}

// 싱글톤 인스턴스
export const apiClient = new ApiClient();
export default apiClient;
