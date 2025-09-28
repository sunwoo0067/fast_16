import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Order, OrderListResponse, OrderFilters, OrderCreateRequest } from '@/types';
import apiClient from '@/services/api';

interface OrdersState {
  // 상태
  orders: Order[];
  total: number;
  currentPage: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  filters: OrderFilters;

  // 액션
  fetchOrders: (page?: number, filters?: OrderFilters) => Promise<void>;
  createOrder: (orderData: OrderCreateRequest) => Promise<void>;
  updateOrderStatus: (orderId: string, status: string, reason?: string) => Promise<void>;
  shipOrder: (orderId: string, trackingNumber: string, shippingCompany: string) => Promise<void>;
  cancelOrder: (orderId: string, reason: string) => Promise<void>;
  setFilters: (filters: Partial<OrderFilters>) => void;
  setPageSize: (size: number) => void;
  clearError: () => void;
}

export const useOrdersStore = create<OrdersState>()(
  devtools(
    (set, get) => ({
      // 초기 상태
      orders: [],
      total: 0,
      currentPage: 1,
      pageSize: 20,
      loading: false,
      error: null,
      filters: {},

      // 액션들
      fetchOrders: async (page = 1, filters = {}) => {
        set({ loading: true, error: null });

        const mergedFilters = { ...get().filters, ...filters };
        const offset = (page - 1) * get().pageSize;

        try {
          const response = await apiClient.getOrders({
            ...mergedFilters,
            limit: get().pageSize,
            offset
          });

          set({
            orders: response.orders,
            total: response.total,
            currentPage: page,
            filters: mergedFilters,
            loading: false
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '주문 목록 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      createOrder: async (orderData: OrderCreateRequest) => {
        set({ loading: true, error: null });
        try {
          await apiClient.createOrder(orderData);
          // 주문 생성 성공 후 목록 새로고침
          get().fetchOrders(get().currentPage);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '주문 생성 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      updateOrderStatus: async (orderId: string, status: string, reason?: string) => {
        set({ loading: true, error: null });
        try {
          await apiClient.updateOrderStatus(orderId, status, reason);
          // 상태 업데이트 성공 후 목록 새로고침
          get().fetchOrders(get().currentPage);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '주문 상태 업데이트 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      shipOrder: async (orderId: string, trackingNumber: string, shippingCompany: string) => {
        set({ loading: true, error: null });
        try {
          await apiClient.shipOrder(orderId, trackingNumber, shippingCompany);
          // 발송 처리 성공 후 목록 새로고침
          get().fetchOrders(get().currentPage);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '주문 발송 처리 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      cancelOrder: async (orderId: string, reason: string) => {
        set({ loading: true, error: null });
        try {
          await apiClient.cancelOrder(orderId, reason);
          // 취소 처리 성공 후 목록 새로고침
          get().fetchOrders(get().currentPage);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '주문 취소 처리 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      setFilters: (newFilters: Partial<OrderFilters>) => {
        const currentFilters = get().filters;
        set({ filters: { ...currentFilters, ...newFilters } });
      },

      setPageSize: (size: number) => {
        set({ pageSize: size });
        get().fetchOrders(1); // 페이지 크기 변경 시 첫 페이지로 이동
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'orders-store',
    }
  )
);
