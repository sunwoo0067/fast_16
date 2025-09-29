from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from app.models.database import get_db
from app.services.price_policy_service import PricePolicyService
from app.core.exceptions import create_http_exception, ProductSyncError, ValidationError
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Pydantic 모델들
class PricePolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    supplier_id: str = Field(..., min_length=1)
    category_id: Optional[str] = None
    base_margin_rate: float = Field(0.3, ge=0.0, le=1.0)
    min_margin_rate: float = Field(0.1, ge=0.0, le=1.0)
    max_margin_rate: float = Field(0.5, ge=0.0, le=1.0)
    price_calculation_method: str = Field("margin", pattern="^(margin|markup|fixed)$")
    rounding_method: str = Field("round", pattern="^(round|floor|ceiling)$")
    discount_rate: float = Field(0.0, ge=0.0, le=1.0)
    premium_rate: float = Field(0.0, ge=0.0, le=1.0)
    min_price: int = Field(0, ge=0)
    max_price: int = Field(10000000, gt=0)
    priority: int = Field(0, ge=0)
    conditions: Optional[Dict[str, Any]] = None
    is_active: bool = True

class PricePolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category_id: Optional[str] = None
    base_margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_margin_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    price_calculation_method: Optional[str] = Field(None, pattern="^(margin|markup|fixed)$")
    rounding_method: Optional[str] = Field(None, pattern="^(round|floor|ceiling)$")
    discount_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    premium_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_price: Optional[int] = Field(None, ge=0)
    max_price: Optional[int] = Field(None, gt=0)
    priority: Optional[int] = Field(None, ge=0)
    conditions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class PricePolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    supplier_id: Optional[str]
    category_id: Optional[str]
    base_margin_rate: float
    min_margin_rate: float
    max_margin_rate: float
    price_calculation_method: str
    rounding_method: str
    discount_rate: float
    premium_rate: float
    min_price: int
    max_price: int
    priority: int
    conditions: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class PriceCalculationRequest(BaseModel):
    product_id: str
    policy_id: str
    original_price: int = Field(..., gt=0)
    created_by: str = "system"

class BulkPriceCalculationRequest(BaseModel):
    product_ids: List[str]
    policy_id: str
    created_by: str = "system"

class PricePolicyQueryParams(BaseModel):
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0)
    supplier_id: Optional[str] = None
    category_id: Optional[str] = None
    is_active: Optional[bool] = None
    search: Optional[str] = None  # 정책명 검색

@router.post("/", response_model=PricePolicyResponse)
async def create_price_policy(
    policy_data: PricePolicyCreate,
    db: AsyncSession = Depends(get_db)
):
    """가격 정책 생성"""
    try:
        logger.info(f"가격 정책 생성 요청: {policy_data.name}")
        policy_service = PricePolicyService(db)

        policy = await policy_service.create_price_policy(
            name=policy_data.name,
            description=policy_data.description,
            supplier_id=policy_data.supplier_id,
            category_id=policy_data.category_id,
            base_margin_rate=policy_data.base_margin_rate,
            min_margin_rate=policy_data.min_margin_rate,
            max_margin_rate=policy_data.max_margin_rate,
            price_calculation_method=policy_data.price_calculation_method,
            rounding_method=policy_data.rounding_method,
            discount_rate=policy_data.discount_rate,
            premium_rate=policy_data.premium_rate,
            min_price=policy_data.min_price,
            max_price=policy_data.max_price,
            priority=policy_data.priority,
            conditions=policy_data.conditions,
            is_active=policy_data.is_active
        )

        logger.info(f"가격 정책 생성 완료: ID={policy.id}")
        return PricePolicyResponse(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            supplier_id=policy.supplier_id,
            category_id=policy.category_id,
            base_margin_rate=policy.base_margin_rate,
            min_margin_rate=policy.min_margin_rate,
            max_margin_rate=policy.max_margin_rate,
            price_calculation_method=policy.price_calculation_method,
            rounding_method=policy.rounding_method,
            discount_rate=policy.discount_rate,
            premium_rate=policy.premium_rate,
            min_price=policy.min_price,
            max_price=policy.max_price,
            priority=policy.priority,
            conditions=json.loads(policy.conditions) if policy.conditions else None,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at
        )

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"가격 정책 생성 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 정책 생성 실패: {str(e)}"))

@router.get("/", response_model=List[PricePolicyResponse])
async def get_price_policies(
    params: PricePolicyQueryParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """가격 정책 목록 조회"""
    try:
        policy_service = PricePolicyService(db)
        policies = await policy_service.get_price_policies(
            supplier_id=params.supplier_id,
            category_id=params.category_id,
            is_active=params.is_active,
            search=params.search,
            limit=params.limit,
            offset=params.offset
        )

        return [
            PricePolicyResponse(
                id=policy.id,
                name=policy.name,
                description=policy.description,
                supplier_id=policy.supplier_id,
                category_id=policy.category_id,
                base_margin_rate=policy.base_margin_rate,
                min_margin_rate=policy.min_margin_rate,
                max_margin_rate=policy.max_margin_rate,
                price_calculation_method=policy.price_calculation_method,
                rounding_method=policy.rounding_method,
                discount_rate=policy.discount_rate,
                premium_rate=policy.premium_rate,
                min_price=policy.min_price,
                max_price=policy.max_price,
                priority=policy.priority,
                conditions=json.loads(policy.conditions) if policy.conditions else None,
                is_active=policy.is_active,
                created_at=policy.created_at,
                updated_at=policy.updated_at
            )
            for policy in policies
        ]

    except Exception as e:
        logger.error(f"가격 정책 목록 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 정책 목록 조회 실패: {str(e)}"))

@router.get("/{policy_id}", response_model=PricePolicyResponse)
async def get_price_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 가격 정책 조회"""
    try:
        policy_service = PricePolicyService(db)
        policy = await policy_service.get_price_policy_by_id(policy_id)

        if not policy:
            raise HTTPException(status_code=404, detail=f"가격 정책을 찾을 수 없습니다 (ID: {policy_id})")

        return PricePolicyResponse(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            supplier_id=policy.supplier_id,
            category_id=policy.category_id,
            base_margin_rate=policy.base_margin_rate,
            min_margin_rate=policy.min_margin_rate,
            max_margin_rate=policy.max_margin_rate,
            price_calculation_method=policy.price_calculation_method,
            rounding_method=policy.rounding_method,
            discount_rate=policy.discount_rate,
            premium_rate=policy.premium_rate,
            min_price=policy.min_price,
            max_price=policy.max_price,
            priority=policy.priority,
            conditions=json.loads(policy.conditions) if policy.conditions else None,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"가격 정책 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 정책 조회 실패: {str(e)}"))

@router.put("/{policy_id}", response_model=PricePolicyResponse)
async def update_price_policy(
    policy_id: str,
    policy_data: PricePolicyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """가격 정책 정보 수정"""
    try:
        logger.info(f"가격 정책 수정 요청: ID={policy_id}")
        policy_service = PricePolicyService(db)

        policy = await policy_service.update_price_policy(
            policy_id=policy_id,
            name=policy_data.name,
            description=policy_data.description,
            category_id=policy_data.category_id,
            base_margin_rate=policy_data.base_margin_rate,
            min_margin_rate=policy_data.min_margin_rate,
            max_margin_rate=policy_data.max_margin_rate,
            price_calculation_method=policy_data.price_calculation_method,
            rounding_method=policy_data.rounding_method,
            discount_rate=policy_data.discount_rate,
            premium_rate=policy_data.premium_rate,
            min_price=policy_data.min_price,
            max_price=policy_data.max_price,
            priority=policy_data.priority,
            conditions=policy_data.conditions,
            is_active=policy_data.is_active
        )

        if not policy:
            raise HTTPException(status_code=404, detail=f"가격 정책을 찾을 수 없습니다 (ID: {policy_id})")

        logger.info(f"가격 정책 수정 완료: ID={policy_id}")
        return PricePolicyResponse(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            supplier_id=policy.supplier_id,
            category_id=policy.category_id,
            base_margin_rate=policy.base_margin_rate,
            min_margin_rate=policy.min_margin_rate,
            max_margin_rate=policy.max_margin_rate,
            price_calculation_method=policy.price_calculation_method,
            rounding_method=policy.rounding_method,
            discount_rate=policy.discount_rate,
            premium_rate=policy.premium_rate,
            min_price=policy.min_price,
            max_price=policy.max_price,
            priority=policy.priority,
            conditions=json.loads(policy.conditions) if policy.conditions else None,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"가격 정책 수정 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 정책 수정 실패: {str(e)}"))

@router.delete("/{policy_id}")
async def delete_price_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """가격 정책 삭제"""
    try:
        logger.info(f"가격 정책 삭제 요청: ID={policy_id}")
        policy_service = PricePolicyService(db)

        success = await policy_service.delete_price_policy(policy_id)

        if success:
            logger.info(f"가격 정책 삭제 완료: ID={policy_id}")
            return {"message": f"가격 정책이 성공적으로 삭제되었습니다 (ID: {policy_id})"}
        else:
            raise HTTPException(status_code=404, detail=f"가격 정책을 찾을 수 없습니다 (ID: {policy_id})")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"가격 정책 삭제 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 정책 삭제 실패: {str(e)}"))

@router.post("/calculate")
async def calculate_price(
    request: PriceCalculationRequest,
    db: AsyncSession = Depends(get_db)
):
    """가격 계산"""
    try:
        logger.info(f"가격 계산 요청: 상품={request.product_id}, 정책={request.policy_id}")
        policy_service = PricePolicyService(db)

        result = await policy_service.calculate_price(
            product_id=request.product_id,
            policy_id=request.policy_id,
            original_price=request.original_price,
            created_by=request.created_by
        )

        logger.info(f"가격 계산 완료: {request.original_price} -> {result['calculated_price']}")
        return result

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"가격 계산 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 계산 실패: {str(e)}"))

@router.post("/bulk-calculate")
async def bulk_calculate_prices(
    request: BulkPriceCalculationRequest,
    db: AsyncSession = Depends(get_db)
):
    """대량 가격 계산"""
    try:
        logger.info(f"대량 가격 계산 요청: {len(request.product_ids)}개 상품")
        policy_service = PricePolicyService(db)

        result = await policy_service.bulk_calculate_prices(
            product_ids=request.product_ids,
            policy_id=request.policy_id,
            created_by=request.created_by
        )

        logger.info(f"대량 가격 계산 완료: 성공={result['success_count']}, 실패={result['failed_count']}")
        return result

    except Exception as e:
        logger.error(f"대량 가격 계산 실패: {e}")
        raise create_http_exception(ProductSyncError(f"대량 가격 계산 실패: {str(e)}"))

@router.get("/stats/{supplier_id}", response_model=Dict[str, Any])
async def get_price_policy_stats(
    supplier_id: str,
    db: AsyncSession = Depends(get_db)
):
    """가격 정책 통계 조회"""
    try:
        policy_service = PricePolicyService(db)
        stats = await policy_service.get_price_policy_stats(supplier_id)

        return stats

    except Exception as e:
        logger.error(f"가격 정책 통계 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 정책 통계 조회 실패: {str(e)}"))

@router.get("/history/", response_model=List[Dict[str, Any]])
async def get_price_calculation_history(
    product_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """가격 계산 이력 조회"""
    try:
        policy_service = PricePolicyService(db)
        history = await policy_service.get_price_calculation_history(
            product_id=product_id,
            policy_id=policy_id,
            limit=limit,
            offset=offset
        )

        return [
            {
                "id": record.id,
                "product_id": record.product_id,
                "policy_id": record.policy_id,
                "original_price": record.original_price,
                "calculated_price": record.calculated_price,
                "margin_rate": record.margin_rate,
                "discount_amount": record.discount_amount,
                "premium_amount": record.premium_amount,
                "calculation_steps": json.loads(record.calculation_steps) if record.calculation_steps else None,
                "calculation_method": record.calculation_method,
                "applied_rules": json.loads(record.applied_rules) if record.applied_rules else None,
                "created_by": record.created_by,
                "created_at": record.created_at
            }
            for record in history
        ]

    except Exception as e:
        logger.error(f"가격 계산 이력 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"가격 계산 이력 조회 실패: {str(e)}"))
