from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.database import get_db
from app.services.category_service import CategoryService
from app.core.exceptions import create_http_exception, ProductSyncError, ValidationError
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Pydantic 모델들
class CategoryCreate(BaseModel):
    category_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=100)
    supplier_id: str = Field(..., min_length=1)
    parent_id: Optional[str] = None
    level: Optional[int] = None
    is_active: bool = True

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[str] = None
    level: Optional[int] = None
    is_active: Optional[bool] = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    parent_id: Optional[str]
    level: int
    supplier_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class CategoryQueryParams(BaseModel):
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0)
    supplier_id: Optional[str] = None
    parent_id: Optional[str] = None
    level: Optional[int] = None
    is_active: Optional[bool] = None
    search: Optional[str] = None  # 카테고리명 검색

@router.post("/", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """카테고리 생성"""
    try:
        logger.info(f"카테고리 생성 요청: {category_data.name}")
        category_service = CategoryService(db)

        category = await category_service.create_category(
            category_id=category_data.category_id,
            name=category_data.name,
            supplier_id=category_data.supplier_id,
            parent_id=category_data.parent_id,
            level=category_data.level,
            is_active=category_data.is_active
        )

        logger.info(f"카테고리 생성 완료: ID={category.id}")
        return CategoryResponse(
            id=category.id,
            name=category.name,
            parent_id=category.parent_id,
            level=category.level,
            supplier_id=category.supplier_id,
            is_active=category.is_active,
            created_at=category.created_at,
            updated_at=category.updated_at
        )

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"카테고리 생성 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 생성 실패: {str(e)}"))

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    params: CategoryQueryParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """카테고리 목록 조회"""
    try:
        category_service = CategoryService(db)
        categories = await category_service.get_categories(
            supplier_id=params.supplier_id,
            parent_id=params.parent_id,
            level=params.level,
            is_active=params.is_active,
            search=params.search,
            limit=params.limit,
            offset=params.offset
        )

        return [
            CategoryResponse(
                id=category.id,
                name=category.name,
                parent_id=category.parent_id,
                level=category.level,
                supplier_id=category.supplier_id,
                is_active=category.is_active,
                created_at=category.created_at,
                updated_at=category.updated_at
            )
            for category in categories
        ]

    except Exception as e:
        logger.error(f"카테고리 목록 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 목록 조회 실패: {str(e)}"))

@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 카테고리 조회"""
    try:
        category_service = CategoryService(db)
        category = await category_service.get_category_by_id(category_id)

        if not category:
            raise HTTPException(status_code=404, detail=f"카테고리를 찾을 수 없습니다 (ID: {category_id})")

        return CategoryResponse(
            id=category.id,
            name=category.name,
            parent_id=category.parent_id,
            level=category.level,
            supplier_id=category.supplier_id,
            is_active=category.is_active,
            created_at=category.created_at,
            updated_at=category.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 조회 실패: {str(e)}"))

@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    category_data: CategoryUpdate,
    db: AsyncSession = Depends(get_db)
):
    """카테고리 정보 수정"""
    try:
        logger.info(f"카테고리 수정 요청: ID={category_id}")
        category_service = CategoryService(db)

        category = await category_service.update_category(
            category_id=category_id,
            name=category_data.name,
            parent_id=category_data.parent_id,
            level=category_data.level,
            is_active=category_data.is_active
        )

        if not category:
            raise HTTPException(status_code=404, detail=f"카테고리를 찾을 수 없습니다 (ID: {category_id})")

        logger.info(f"카테고리 수정 완료: ID={category_id}")
        return CategoryResponse(
            id=category.id,
            name=category.name,
            parent_id=category.parent_id,
            level=category.level,
            supplier_id=category.supplier_id,
            is_active=category.is_active,
            created_at=category.created_at,
            updated_at=category.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 수정 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 수정 실패: {str(e)}"))

@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db)
):
    """카테고리 삭제"""
    try:
        logger.info(f"카테고리 삭제 요청: ID={category_id}")
        category_service = CategoryService(db)

        success = await category_service.delete_category(category_id)

        if success:
            logger.info(f"카테고리 삭제 완료: ID={category_id}")
            return {"message": f"카테고리가 성공적으로 삭제되었습니다 (ID: {category_id})"}
        else:
            raise HTTPException(status_code=404, detail=f"카테고리를 찾을 수 없습니다 (ID: {category_id})")

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 삭제 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 삭제 실패: {str(e)}"))

@router.get("/tree/{supplier_id}", response_model=Dict[str, Any])
async def get_category_tree(
    supplier_id: str,
    db: AsyncSession = Depends(get_db)
):
    """계층형 카테고리 트리 구조 조회"""
    try:
        category_service = CategoryService(db)
        tree = await category_service.get_category_tree(supplier_id)

        return tree

    except Exception as e:
        logger.error(f"카테고리 트리 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 트리 조회 실패: {str(e)}"))

@router.get("/stats/{supplier_id}", response_model=Dict[str, Any])
async def get_category_stats(
    supplier_id: str,
    db: AsyncSession = Depends(get_db)
):
    """카테고리 통계 조회"""
    try:
        category_service = CategoryService(db)
        stats = await category_service.get_category_stats(supplier_id)

        return stats

    except Exception as e:
        logger.error(f"카테고리 통계 조회 실패: {e}")
        raise create_http_exception(ProductSyncError(f"카테고리 통계 조회 실패: {str(e)}"))
