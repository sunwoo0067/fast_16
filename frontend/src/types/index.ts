// API 응답 타입들
export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  timestamp: string;
}

// 상품 관련 타입들
export interface Product {
  id: string;
  title: string;
  brand: string;
  price: number;
  sale_price?: number;
  margin_rate: number;
  stock_quantity: number;
  max_stock_quantity?: number;
  images: string[];
  category_id: string;
  supplier_id: string;
  description?: string;
  is_active: boolean;
  sync_status: string;
  last_synced_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

// 주문 관련 타입들
export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  options: Record<string, any>;
}

export interface Order {
  id: string;
  supplier_id: string;
  supplier_account_id: string;
  order_key: string;
  status: string;
  payment_status: string;
  items: OrderItem[];
  subtotal: number;
  shipping_fee: number;
  total_amount: number;
  customer_name?: string;
  customer_phone?: string;
  shipping_address?: Record<string, any>;
  shipping_info: {
    tracking_number?: string;
    shipping_company?: string;
    shipped_at?: string;
    estimated_delivery_date?: string;
    actual_delivery_date?: string;
  };
  orderer_note?: string;
  seller_note?: string;
  created_at: string;
  updated_at: string;
}

export interface OrderListResponse {
  orders: Order[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

// 공급사 관련 타입들
export interface Supplier {
  id: number;
  name: string;
  description?: string;
  is_active: boolean;
  api_key?: string;
  base_url?: string;
  created_at: string;
  updated_at: string;
}

export interface SupplierAccount {
  id: number;
  supplier_id: number;
  account_name: string;
  username: string;
  is_active: boolean;
  usage_count: number;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate: number;
  default_margin_rate: number;
  sync_enabled: boolean;
  last_used_at?: string;
  last_sync_at?: string;
  created_at: string;
  updated_at: string;
}

// 동기화 관련 타입들
export interface SyncHistory {
  id: string;
  item_id?: string;
  supplier_id?: string;
  market_type?: string;
  sync_type: string;
  status: string;
  result?: {
    success_count: number;
    failure_count: number;
    total_count: number;
    success_rate: number;
    errors: Record<string, string>;
  };
  details?: Record<string, any>;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  retry_count: number;
  max_retries: number;
  created_at: string;
}

// 통계 관련 타입들
export interface DashboardStats {
  total_products: number;
  active_products: number;
  sync_products: number;
  failed_products: number;
  total_orders: number;
  pending_orders: number;
  shipped_orders: number;
  delivered_orders: number;
  total_revenue: number;
  average_order_value: number;
  recent_syncs: SyncHistory[];
}

// 필터 및 검색 타입들
export interface ProductFilters {
  supplier_id?: string;
  category_id?: string;
  is_active?: boolean;
  sync_status?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface OrderFilters {
  supplier_id?: string;
  status?: string;
  payment_status?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

// API 요청/응답 타입들
export interface ProductSyncRequest {
  supplier_id: string;
  item_keys?: string[];
  dry_run?: boolean;
}

export interface ProductSyncResponse {
  success: boolean;
  message: string;
  processed_count: number;
  success_count: number;
  failure_count: number;
  errors: Array<{item_id: string; error: string}>;
}

export interface OrderCreateRequest {
  supplier_id: string;
  supplier_account_id: string;
  order_key: string;
  items: Array<{
    product_id: string;
    product_name: string;
    quantity: number;
    unit_price: number;
    options?: Record<string, any>;
  }>;
  shipping_fee?: number;
  customer_name?: string;
  customer_phone?: string;
  shipping_address?: Record<string, any>;
  orderer_note?: string;
}

export interface SupplierTestRequest {
  supplier_id: number;
  account_name: string;
}

// 컴포넌트 Props 타입들
export interface TableColumn<T = any> {
  key: string;
  title: string;
  dataIndex?: string;
  render?: (value: any, record: T, index: number) => React.ReactNode;
  width?: number;
  sorter?: boolean;
  filter?: boolean;
}

export interface PaginationConfig {
  current: number;
  pageSize: number;
  total: number;
  showSizeChanger: boolean;
  showQuickJumper: boolean;
  showTotal: (total: number, range: [number, number]) => string;
}

// 로딩 및 에러 상태
export interface LoadingState {
  loading: boolean;
  error: string | null;
}

// 테마 및 UI 설정
export interface ThemeConfig {
  primaryColor: string;
  fontSize: 'small' | 'medium' | 'large';
  compact: boolean;
  darkMode: boolean;
}
