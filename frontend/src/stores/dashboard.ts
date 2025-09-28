import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { DashboardStats, Product, Order, Supplier, SyncHistory } from '@/types';
import apiClient from '@/services/api';

interface DashboardState {
  // 상태
  stats: DashboardStats | null;
  recentProducts: Product[];
  recentOrders: Order[];
  recentSyncs: SyncHistory[];
  loading: boolean;
  error: string | null;

  // 액션
  fetchStats: () => Promise<void>;
  fetchRecentProducts: () => Promise<void>;
  fetchRecentOrders: () => Promise<void>;
  fetchRecentSyncs: () => Promise<void>;
  clearError: () => void;
}

export const useDashboardStore = create<DashboardState>()(
  devtools(
    (set, get) => ({
      // 초기 상태
      stats: null,
      recentProducts: [],
      recentOrders: [],
      recentSyncs: [],
      loading: false,
      error: null,

      // 액션들
      fetchStats: async () => {
        set({ loading: true, error: null });
        try {
          const stats = await apiClient.getDashboardStats();
          set({ stats, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '통계 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      fetchRecentProducts: async () => {
        set({ loading: true, error: null });
        try {
          const response = await apiClient.getProducts({ limit: 10 });
          set({ recentProducts: response.items, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '최근 상품 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      fetchRecentOrders: async () => {
        set({ loading: true, error: null });
        try {
          const response = await apiClient.getOrders({ limit: 10 });
          set({ recentOrders: response.orders, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '최근 주문 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      fetchRecentSyncs: async () => {
        set({ loading: true, error: null });
        try {
          const syncs = await apiClient.getSyncHistory({ limit: 10 });
          set({ recentSyncs: syncs, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '최근 동기화 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'dashboard-store',
    }
  )
);
