"""저장소 포트 (인터페이스)"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Item:
    """표준화된 상품 엔티티"""
    id: str
    title: str
    brand: str
    price: Dict[str, Any]
    options: List[Dict[str, Any]]
    images: List[str]
    category_id: str
    supplier_id: str
    normalized_at: datetime
    hash_key: str  # 중복 검사용


@dataclass
class SupplierAccount:
    """공급사 계정 정보"""
    id: str
    supplier_id: str
    account_name: str
    username: str
    password_encrypted: str
    api_credentials: Optional[Dict[str, str]] = None
    is_active: bool = True
    last_used_at: Optional[datetime] = None


@dataclass
class MarketAccount:
    """마켓 계정 정보"""
    id: str
    market_type: str
    account_name: str
    api_key: str
    api_secret: str
    vendor_id: Optional[str] = None
    is_active: bool = True
    last_used_at: Optional[datetime] = None


@dataclass
class ProductSyncHistory:
    """상품 동기화 이력"""
    id: str
    item_id: str
    supplier_id: str
    sync_type: str  # 'ingest', 'normalize', 'upload'
    status: str  # 'success', 'failed', 'pending'
    details: Optional[Dict[str, Any]] = None
    synced_at: datetime = None


class RepositoryPort(ABC):
    """저장소 인터페이스"""

    # Item 관련
    @abstractmethod
    async def save_item(self, item: Item) -> None:
        """상품 저장"""
        pass

    @abstractmethod
    async def get_item_by_id(self, item_id: str) -> Optional[Item]:
        """상품 ID로 조회"""
        pass

    @abstractmethod
    async def get_items_by_supplier(
        self,
        supplier_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Item]:
        """공급사별 상품 목록 조회"""
        pass

    @abstractmethod
    async def find_item_by_hash(self, hash_key: str) -> Optional[Item]:
        """해시로 상품 중복 체크"""
        pass

    @abstractmethod
    async def update_item(self, item_id: str, updates: Dict[str, Any]) -> None:
        """상품 업데이트"""
        pass

    # Account 관련
    @abstractmethod
    async def save_supplier_account(self, account: SupplierAccount) -> None:
        """공급사 계정 저장"""
        pass

    @abstractmethod
    async def get_supplier_account(self, supplier_id: str, account_name: str) -> Optional[SupplierAccount]:
        """공급사 계정 조회"""
        pass

    @abstractmethod
    async def save_market_account(self, account: MarketAccount) -> None:
        """마켓 계정 저장"""
        pass

    @abstractmethod
    async def get_market_account(self, market_type: str, account_name: str) -> Optional[MarketAccount]:
        """마켓 계정 조회"""
        pass

    # Sync History 관련
    @abstractmethod
    async def save_sync_history(self, history: ProductSyncHistory) -> None:
        """동기화 이력 저장"""
        pass

    @abstractmethod
    async def get_sync_history(
        self,
        item_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        sync_type: Optional[str] = None,
        limit: int = 50
    ) -> List[ProductSyncHistory]:
        """동기화 이력 조회"""
        pass
