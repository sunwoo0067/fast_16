from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.database import get_db
from app.utils.async_task import (
    task_manager,
    TaskStatus,
    create_bulk_product_task,
    create_product_collection_task
)
from app.core.exceptions import create_http_exception
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Pydantic 모델들
class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: float
    progress_message: str
    retry_count: int
    max_retries: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    result: Optional[Dict[str, Any]]
    error: Optional[str]

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    pending: int
    running: int
    completed: int
    failed: int

class BulkProductRequest(BaseModel):
    products_data: List[Dict[str, Any]]
    supplier_id: int
    supplier_account_id: int

class ProductCollectionRequest(BaseModel):
    supplier_id: int
    supplier_account_id: Optional[int] = None
    item_keys: Optional[List[str]] = None
    force_sync: bool = False

@router.get("/", response_model=TaskListResponse)
async def get_tasks(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """작업 목록 조회"""
    try:
        # 상태 필터링
        if status_filter:
            try:
                status_enum = TaskStatus(status_filter)
                filtered_tasks = task_manager.get_tasks_by_status(status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"유효하지 않은 상태: {status_filter}"
                )
        else:
            filtered_tasks = task_manager.get_all_tasks()

        # 페이징 적용
        task_items = list(filtered_tasks.items())
        total_tasks = len(task_items)

        # 상태별 카운트
        status_counts = {
            TaskStatus.PENDING: len(task_manager.get_tasks_by_status(TaskStatus.PENDING)),
            TaskStatus.RUNNING: len(task_manager.get_tasks_by_status(TaskStatus.RUNNING)),
            TaskStatus.COMPLETED: len(task_manager.get_tasks_by_status(TaskStatus.COMPLETED)),
            TaskStatus.FAILED: len(task_manager.get_tasks_by_status(TaskStatus.FAILED)),
        }

        # 페이징된 결과
        start_idx = offset
        end_idx = offset + limit
        paginated_tasks = task_items[start_idx:end_idx]

        tasks = [
            TaskResponse(**task_data.to_dict())
            for task_id, task_data in paginated_tasks
        ]

        return TaskListResponse(
            tasks=tasks,
            total=total_tasks,
            pending=status_counts[TaskStatus.PENDING],
            running=status_counts[TaskStatus.RUNNING],
            completed=status_counts[TaskStatus.COMPLETED],
            failed=status_counts[TaskStatus.FAILED]
        )

    except Exception as e:
        logger.error(f"작업 목록 조회 실패: {e}")
        raise create_http_exception(Exception(f"작업 목록 조회 실패: {str(e)}"))

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """특정 작업 조회"""
    try:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"작업을 찾을 수 없습니다: {task_id}"
            )

        return TaskResponse(**task.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 조회 실패: {e}")
        raise create_http_exception(Exception(f"작업 조회 실패: {str(e)}"))

@router.post("/bulk-products", response_model=Dict[str, str])
async def create_bulk_product_task_endpoint(
    request: BulkProductRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """대량 상품 등록 작업 생성"""
    try:
        logger.info(f"대량 상품 등록 작업 요청: {len(request.products_data)}개 상품")

        # 작업 생성
        task_id = create_bulk_product_task(
            products_data=request.products_data,
            supplier_id=request.supplier_id,
            supplier_account_id=request.supplier_account_id
        )

        # 백그라운드에서 작업 관리자 시작
        background_tasks.add_task(_start_task_manager)

        return {
            "message": "대량 상품 등록 작업이 생성되었습니다",
            "task_id": task_id
        }

    except Exception as e:
        logger.error(f"대량 상품 등록 작업 생성 실패: {e}")
        raise create_http_exception(Exception(f"작업 생성 실패: {str(e)}"))

@router.post("/product-collection", response_model=Dict[str, str])
async def create_product_collection_task_endpoint(
    request: ProductCollectionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """상품 수집 작업 생성"""
    try:
        logger.info(f"상품 수집 작업 요청: supplier_id={request.supplier_id}")

        # 작업 생성
        task_id = create_product_collection_task(
            supplier_id=request.supplier_id,
            supplier_account_id=request.supplier_account_id,
            item_keys=request.item_keys,
            force_sync=request.force_sync
        )

        # 백그라운드에서 작업 관리자 시작
        background_tasks.add_task(_start_task_manager)

        return {
            "message": "상품 수집 작업이 생성되었습니다",
            "task_id": task_id
        }

    except Exception as e:
        logger.error(f"상품 수집 작업 생성 실패: {e}")
        raise create_http_exception(Exception(f"작업 생성 실패: {str(e)}"))

@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """작업 취소"""
    try:
        cancelled = task_manager.cancel_task(task_id)
        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"취소할 수 있는 작업을 찾을 수 없습니다: {task_id}"
            )

        return {"message": "작업이 취소되었습니다", "task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 취소 실패: {e}")
        raise create_http_exception(Exception(f"작업 취소 실패: {str(e)}"))

@router.post("/cleanup")
async def cleanup_tasks():
    """완료된 작업 정리"""
    try:
        cleaned_count = task_manager.cleanup_completed_tasks(older_than_hours=24)

        return {
            "message": f"{cleaned_count}개의 완료된 작업이 정리되었습니다",
            "cleaned_count": cleaned_count
        }

    except Exception as e:
        logger.error(f"작업 정리 실패: {e}")
        raise create_http_exception(Exception(f"작업 정리 실패: {str(e)}"))

@router.get("/stats/summary")
async def get_task_stats():
    """작업 통계 조회"""
    try:
        all_tasks = task_manager.get_all_tasks()

        stats = {
            "total": len(all_tasks),
            "pending": len(task_manager.get_tasks_by_status(TaskStatus.PENDING)),
            "running": len(task_manager.get_tasks_by_status(TaskStatus.RUNNING)),
            "completed": len(task_manager.get_tasks_by_status(TaskStatus.COMPLETED)),
            "failed": len(task_manager.get_tasks_by_status(TaskStatus.FAILED)),
            "cancelled": len(task_manager.get_tasks_by_status(TaskStatus.CANCELLED))
        }

        # 성공률 계산
        completed_tasks = [task for task in all_tasks.values() if task.status == TaskStatus.COMPLETED]
        failed_tasks = [task for task in all_tasks.values() if task.status == TaskStatus.FAILED]

        total_finished = len(completed_tasks) + len(failed_tasks)
        if total_finished > 0:
            stats["success_rate"] = len(completed_tasks) / total_finished * 100
        else:
            stats["success_rate"] = 0.0

        # 평균 처리 시간
        durations = [
            task.duration_seconds for task in all_tasks.values()
            if task.duration_seconds is not None
        ]
        if durations:
            stats["avg_duration_seconds"] = sum(durations) / len(durations)
        else:
            stats["avg_duration_seconds"] = 0.0

        return stats

    except Exception as e:
        logger.error(f"작업 통계 조회 실패: {e}")
        raise create_http_exception(Exception(f"작업 통계 조회 실패: {str(e)}"))

async def _start_task_manager():
    """백그라운드에서 작업 관리자 시작"""
    try:
        await task_manager.start()
    except Exception as e:
        logger.error(f"작업 관리자 시작 실패: {e}")
