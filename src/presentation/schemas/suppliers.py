"""공급사 관련 DTO 스키마"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SupplierCreateRequest(BaseModel):
    """공급사 생성 요청"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None


class SupplierUpdateRequest(BaseModel):
    """공급사 업데이트 요청"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    """공급사 응답"""
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    api_key: Optional[str]
    base_url: Optional[str]
    created_at: datetime
    updated_at: datetime


class SupplierAccountCreateRequest(BaseModel):
    """공급사 계정 생성 요청"""
    supplier_id: int
    account_name: str = Field(..., min_length=1, max_length=100)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    default_margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    sync_enabled: Optional[bool] = True


class SupplierAccountUpdateRequest(BaseModel):
    """공급사 계정 업데이트 요청"""
    account_name: Optional[str] = Field(None, min_length=1, max_length=100)
    username: Optional[str] = Field(None, min_length=1)
    password: Optional[str] = Field(None, min_length=1)
    default_margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    sync_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class SupplierAccountResponse(BaseModel):
    """공급사 계정 응답"""
    id: int
    supplier_id: int
    account_name: str
    username: str
    is_active: bool
    usage_count: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    default_margin_rate: float
    sync_enabled: bool
    last_used_at: Optional[datetime]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class SupplierAccountListResponse(BaseModel):
    """공급사 계정 목록 응답"""
    accounts: List[SupplierAccountResponse]
    total: int
    page: int
    page_size: int


class SupplierTestRequest(BaseModel):
    """공급사 연결 테스트 요청"""
    supplier_id: int
    account_name: str


class SupplierTestResponse(BaseModel):
    """공급사 연결 테스트 응답"""
    success: bool
    message: str
    account_info: Optional[dict] = None
