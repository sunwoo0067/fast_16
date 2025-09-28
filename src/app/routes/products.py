"""상품 관련 라우트 (헥사고날 아키텍처)"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from src.app.di import (
    get_ingest_items_usecase,
    get_normalize_items_usecase,
    get_publish_to_market_usecase,
    get_item_service
)
from src.core.usecases.ingest_items import IngestItemsUseCase
from src.core.usecases.normalize_items import NormalizeItemsUseCase
from src.core.usecases.publish_to_market import PublishToMarketUseCase
from src.services.item_service import ItemService
from src.core.ports.market_port import MarketType
from src.presentation.schemas.items import (
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductResponse,
    ProductListResponse,
    ProductSyncRequest,
    ProductSyncResponse,
    IngestItemsRequest,
    IngestItemsResponse,
    NormalizeItemsRequest,
    NormalizeItemsResponse,
    PublishToMarketRequest,
    PublishToMarketResponse
)
from src.shared.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/ingest", response_model=IngestItemsResponse)
async def ingest_items(
    request: IngestItemsRequest,
    usecase: IngestItemsUseCase = Depends(get_ingest_items_usecase)
):
    """상품 수집 (헥사고날 아키텍처)"""
    try:
        result = await usecase.execute(
            supplier_id=request.supplier_id,
            account_id=request.account_id,
            item_keys=request.item_keys
        )

        if result.is_success():
            return IngestItemsResponse(
                success=True,
                message=f"상품 수집 완료: {len(result.get_value())}개",
                items_count=len(result.get_value()),
                processed_items=[item.id for item in result.get_value()]
            )
        else:
            return IngestItemsResponse(
                success=False,
                message=result.get_error(),
                items_count=0
            )

    except Exception as e:
        logger.error(f"상품 수집 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/normalize", response_model=NormalizeItemsResponse)
async def normalize_items(
    request: NormalizeItemsRequest,
    usecase: NormalizeItemsUseCase = Depends(get_normalize_items_usecase)
):
    """상품 정규화 (헥사고날 아키텍처)"""
    try:
        result = await usecase.execute(
            supplier_id=request.supplier_id,
            item_ids=request.item_ids,
            batch_size=request.batch_size
        )

        if result.is_success():
            return NormalizeItemsResponse(
                success=True,
                message=f"상품 정규화 완료: {len(result.get_value())}개",
                processed_count=len(result.get_value()),
                normalized_count=len(result.get_value())
            )
        else:
            return NormalizeItemsResponse(
                success=False,
                message=result.get_error(),
                processed_count=0,
                normalized_count=0
            )

    except Exception as e:
        logger.error(f"상품 정규화 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/publish", response_model=PublishToMarketResponse)
async def publish_to_market(
    request: PublishToMarketRequest,
    usecase: PublishToMarketUseCase = Depends(get_publish_to_market_usecase)
):
    """마켓 업로드 (헥사고날 아키텍처)"""
    try:
        # 마켓 타입 검증
        try:
            market_type = MarketType(request.market_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 마켓 타입: {request.market_type}"
            )

        result = await usecase.execute(
            market_type=market_type,
            item_ids=request.item_ids,
            account_name=request.account_name,
            dry_run=request.dry_run
        )

        if result.is_success():
            return PublishToMarketResponse(
                success=True,
                message=f"마켓 업로드 완료: {len(result.get_value())}개",
                processed_count=len(result.get_value()),
                success_count=len(result.get_value()),
                failure_count=0,
                results=result.get_value()
            )
        else:
            return PublishToMarketResponse(
                success=False,
                message=result.get_error(),
                processed_count=0,
                success_count=0,
                failure_count=0
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"마켓 업로드 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=ProductListResponse)
async def get_products(
    supplier_id: Optional[str] = None,
    category_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    sync_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    item_service: ItemService = Depends(get_item_service)
):
    """상품 목록 조회 (헥사고날 아키텍처)"""
    return await item_service.get_products(
        supplier_id=supplier_id,
        category_id=category_id,
        is_active=is_active,
        sync_status=sync_status,
        search=search,
        limit=limit,
        offset=offset
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    item_service: ItemService = Depends(get_item_service)
):
    """상품 상세 조회 (헥사고날 아키텍처)"""
    result = await item_service.get_product(product_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상품을 찾을 수 없습니다"
        )
    return result


@router.post("", response_model=ProductResponse)
async def create_product(request: ProductCreateRequest):
    """상품 생성 (헥사고날 아키텍처)"""
    # TODO: 상품 생성 유즈케이스 구현 후 연결
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="아직 구현되지 않은 기능입니다"
    )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, request: ProductUpdateRequest):
    """상품 수정 (헥사고날 아키텍처)"""
    # TODO: 상품 수정 유즈케이스 구현 후 연결
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="아직 구현되지 않은 기능입니다"
    )


@router.delete("/{product_id}")
async def delete_product(product_id: int):
    """상품 삭제 (헥사고날 아키텍처)"""
    # TODO: 상품 삭제 유즈케이스 구현 후 연결
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="아직 구현되지 않은 기능입니다"
    )


@router.post("/{product_id}/sync", response_model=ProductSyncResponse)
async def sync_product(product_id: int, background_tasks: BackgroundTasks):
    """상품 동기화 (헥사고날 아키텍처)"""
    # TODO: 상품 동기화 유즈케이스 구현 후 연결
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="아직 구현되지 않은 기능입니다"
    )
