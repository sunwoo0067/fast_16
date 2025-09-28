"""공급사 연동 포트 (인터페이스)"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawItemData:
    """공급사에서 받은 원본 상품 데이터"""
    id: str
    title: str
    brand: str
    price: Dict[str, Any]
    options: List[Dict[str, Any]]
    images: List[str]
    category: str
    description: Optional[str] = None
    supplier_id: str = ""
    fetched_at: datetime = None


@dataclass
class SupplierCredentials:
    """공급사 인증 정보"""
    supplier_id: str
    account_id: str
    username: str
    password: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class SupplierPort(ABC):
    """공급사 연동 인터페이스"""

    @abstractmethod
    async def authenticate(self, credentials: SupplierCredentials) -> str:
        """공급사 인증 및 토큰 발급"""
        pass

    @abstractmethod
    async def fetch_items(
        self,
        supplier_id: str,
        account_id: str,
        item_keys: Optional[List[str]] = None
    ) -> List[RawItemData]:
        """상품 데이터 수집"""
        pass

    @abstractmethod
    async def get_categories(self, supplier_id: str, account_id: str) -> List[Dict[str, Any]]:
        """카테고리 정보 조회"""
        pass

    @abstractmethod
    async def check_credentials(self, credentials: SupplierCredentials) -> bool:
        """인증 정보 유효성 검증"""
        pass
