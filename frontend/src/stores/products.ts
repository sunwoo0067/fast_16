import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Product, ProductListResponse, ProductFilters, ProductSyncRequest } from '@/types';
import apiClient from '@/services/api';

interface ProductsState {
  // 상태
  products: Product[];
  total: number;
  currentPage: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  filters: ProductFilters;

  // 액션
  fetchProducts: (page?: number, filters?: ProductFilters) => Promise<void>;
  syncProducts: (request: ProductSyncRequest) => Promise<void>;
  normalizeProducts: (supplierId?: string, itemIds?: string[]) => Promise<void>;
  publishProducts: (marketType: string, itemIds: string[], accountName: string) => Promise<void>;
  setFilters: (filters: Partial<ProductFilters>) => void;
  setPageSize: (size: number) => void;
  clearError: () => void;
}

export const useProductsStore = create<ProductsState>()(
  devtools(
    (set, get) => ({
      // 초기 상태
      products: [],
      total: 0,
      currentPage: 1,
      pageSize: 20,
      loading: false,
      error: null,
      filters: {},

      // 액션들
      fetchProducts: async (page = 1, filters = {}) => {
        set({ loading: true, error: null });

        const mergedFilters = { ...get().filters, ...filters };
        const offset = (page - 1) * get().pageSize;

        try {
          const response = await apiClient.getProducts({
            ...mergedFilters,
            limit: get().pageSize,
            offset
          });

          set({
            products: response.items,
            total: response.total,
            currentPage: page,
            filters: mergedFilters,
            loading: false
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '상품 목록 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      syncProducts: async (request: ProductSyncRequest) => {
        set({ loading: true, error: null });
        try {
          const response = await apiClient.syncProducts(request);
          if (response.success) {
            // 동기화 성공 후 목록 새로고침
            get().fetchProducts(get().currentPage);
          } else {
            set({
              error: response.message || '상품 동기화 중 오류가 발생했습니다.',
              loading: false
            });
          }
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '상품 동기화 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      normalizeProducts: async (supplierId?: string, itemIds?: string[]) => {
        set({ loading: true, error: null });
        try {
          await apiClient.normalizeProducts({ supplier_id: supplierId, item_ids: itemIds });
          // 정규화 성공 후 목록 새로고침
          get().fetchProducts(get().currentPage);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '상품 정규화 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      publishProducts: async (marketType: string, itemIds: string[], accountName: string) => {
        set({ loading: true, error: null });
        try {
          await apiClient.publishProducts({
            market_type: marketType,
            item_ids: itemIds,
            account_name: accountName
          });
          // 업로드 성공 후 목록 새로고침
          get().fetchProducts(get().currentPage);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '상품 업로드 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      setFilters: (newFilters: Partial<ProductFilters>) => {
        const currentFilters = get().filters;
        set({ filters: { ...currentFilters, ...newFilters } });
      },

      setPageSize: (size: number) => {
        set({ pageSize: size });
        get().fetchProducts(1); // 페이지 크기 변경 시 첫 페이지로 이동
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'products-store',
    }
  )
);
