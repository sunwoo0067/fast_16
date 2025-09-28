"""마켓 연동 포트 (인터페이스)"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketType(Enum):
    """지원하는 마켓 타입"""
    COUPANG = "coupang"
    NAVER = "naver"
    ELEVENST = "11st"


@dataclass
class MarketCredentials:
    """마켓 인증 정보"""
    market: MarketType
    account_id: str
    api_key: str
    api_secret: str
    access_token: Optional[str] = None
    vendor_id: Optional[str] = None


@dataclass
class MarketProduct:
    """마켓 상품 정보"""
    id: str
    title: str
    price: int
    stock: int
    images: List[str]
    category_id: str
    attributes: Dict[str, Any]
    description: Optional[str] = None


@dataclass
class UploadResult:
    """상품 업로드 결과"""
    success: bool
    product_id: Optional[str] = None
    error_message: Optional[str] = None
    channel_product_no: Optional[str] = None


@dataclass
class SyncStatus:
    """동기화 상태 정보"""
    last_synced_at: datetime
    status: str
    error_message: Optional[str] = None
    retry_count: int = 0


class MarketPort(ABC):
    """마켓 연동 인터페이스"""

    @abstractmethod
    async def authenticate(self, credentials: MarketCredentials) -> bool:
        """마켓 인증"""
        pass

    @abstractmethod
    async def upload_product(
        self,
        credentials: MarketCredentials,
        product: MarketProduct
    ) -> UploadResult:
        """상품 업로드"""
        pass

    @abstractmethod
    async def update_product(
        self,
        credentials: MarketCredentials,
        product_id: str,
        product: MarketProduct
    ) -> UploadResult:
        """상품 수정"""
        pass

    @abstractmethod
    async def get_product_status(
        self,
        credentials: MarketCredentials,
        product_id: str
    ) -> SyncStatus:
        """상품 동기화 상태 조회"""
        pass

    @abstractmethod
    async def update_inventory(
        self,
        credentials: MarketCredentials,
        product_id: str,
        quantity: int
    ) -> bool:
        """재고 업데이트"""
        pass

    @abstractmethod
    async def update_price(
        self,
        credentials: MarketCredentials,
        product_id: str,
        price: int
    ) -> bool:
        """가격 업데이트"""
        pass
