import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Supplier, SupplierAccount, SupplierTestRequest } from '@/types';
import apiClient from '@/services/api';

interface SuppliersState {
  // 상태
  suppliers: Supplier[];
  currentSupplier: Supplier | null;
  supplierAccounts: SupplierAccount[];
  loading: boolean;
  error: string | null;

  // 액션
  fetchSuppliers: () => Promise<void>;
  fetchSupplier: (supplierId: number) => Promise<void>;
  createSupplier: (supplierData: Partial<Supplier>) => Promise<void>;
  updateSupplier: (supplierId: number, supplierData: Partial<Supplier>) => Promise<void>;
  deleteSupplier: (supplierId: number) => Promise<void>;
  fetchSupplierAccounts: (supplierId: number) => Promise<void>;
  createSupplierAccount: (supplierId: number, accountData: Partial<SupplierAccount>) => Promise<void>;
  testConnection: (request: SupplierTestRequest) => Promise<void>;
  setCurrentSupplier: (supplier: Supplier | null) => void;
  clearError: () => void;
}

export const useSuppliersStore = create<SuppliersState>()(
  devtools(
    (set, get) => ({
      // 초기 상태
      suppliers: [],
      currentSupplier: null,
      supplierAccounts: [],
      loading: false,
      error: null,

      // 액션들
      fetchSuppliers: async () => {
        set({ loading: true, error: null });
        try {
          const suppliers = await apiClient.getSuppliers();
          set({ suppliers, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 목록 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      fetchSupplier: async (supplierId: number) => {
        set({ loading: true, error: null });
        try {
          const supplier = await apiClient.getSupplier(supplierId);
          set({ currentSupplier: supplier, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      createSupplier: async (supplierData: Partial<Supplier>) => {
        set({ loading: true, error: null });
        try {
          await apiClient.createSupplier(supplierData);
          // 생성 성공 후 목록 새로고침
          get().fetchSuppliers();
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 생성 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      updateSupplier: async (supplierId: number, supplierData: Partial<Supplier>) => {
        set({ loading: true, error: null });
        try {
          await apiClient.updateSupplier(supplierId, supplierData);
          // 수정 성공 후 목록 새로고침
          get().fetchSuppliers();
          get().fetchSupplier(supplierId);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 수정 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      deleteSupplier: async (supplierId: number) => {
        set({ loading: true, error: null });
        try {
          await apiClient.deleteSupplier(supplierId);
          // 삭제 성공 후 목록 새로고침
          get().fetchSuppliers();
          if (get().currentSupplier?.id === supplierId) {
            set({ currentSupplier: null });
          }
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 삭제 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      fetchSupplierAccounts: async (supplierId: number) => {
        set({ loading: true, error: null });
        try {
          const accounts = await apiClient.getSupplierAccounts(supplierId);
          set({ supplierAccounts: accounts, loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 계정 목록 조회 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      createSupplierAccount: async (supplierId: number, accountData: Partial<SupplierAccount>) => {
        set({ loading: true, error: null });
        try {
          await apiClient.createSupplierAccount(supplierId, accountData);
          // 계정 생성 성공 후 목록 새로고침
          get().fetchSupplierAccounts(supplierId);
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '공급사 계정 생성 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      testConnection: async (request: SupplierTestRequest) => {
        set({ loading: true, error: null });
        try {
          const result = await apiClient.testSupplierConnection(request);
          if (result.success) {
            // 연결 테스트 성공
            set({ loading: false });
          } else {
            set({
              error: result.message || '연결 테스트에 실패했습니다.',
              loading: false
            });
          }
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || '연결 테스트 중 오류가 발생했습니다.',
            loading: false
          });
        }
      },

      setCurrentSupplier: (supplier: Supplier | null) => {
        set({ currentSupplier: supplier });
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'suppliers-store',
    }
  )
);
