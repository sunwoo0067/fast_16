import asyncio
import uuid
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import json

from app.core.logging import get_logger, LoggerMixin

logger = get_logger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AsyncTask(LoggerMixin):
    """비동기 작업 클래스"""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300  # 5분 타임아웃
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.retry_count = 0
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.progress = 0.0
        self.progress_message = ""

    async def execute(self) -> Any:
        """작업 실행"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

        try:
            # 타임아웃 설정
            result = await asyncio.wait_for(
                self.func(*self.args, **self.kwargs),
                timeout=self.timeout
            )

            self.status = TaskStatus.COMPLETED
            self.result = result
            self.completed_at = datetime.now()

            self.logger.info(f"작업 완료: {self.task_id} ({self.task_type})")
            return result

        except asyncio.TimeoutError:
            self.status = TaskStatus.FAILED
            self.error = f"작업 타임아웃 (제한시간: {self.timeout}초)"
            self.completed_at = datetime.now()

            self.logger.error(f"작업 타임아웃: {self.task_id}")
            raise

        except Exception as e:
            self.retry_count += 1

            if self.retry_count < self.max_retries:
                self.status = TaskStatus.PENDING
                self.logger.warning(f"작업 재시도: {self.task_id} (시도 {self.retry_count}/{self.max_retries})")

                # 재시도 대기
                await asyncio.sleep(self.retry_delay)
                return await self.execute()
            else:
                self.status = TaskStatus.FAILED
                self.error = str(e)
                self.completed_at = datetime.now()

                self.logger.error(f"작업 실패: {self.task_id} - {e}")
                raise

    def update_progress(self, progress: float, message: str = ""):
        """진행률 업데이트"""
        self.progress = max(0.0, min(1.0, progress))  # 0-1 범위로 제한
        self.progress_message = message

    def to_dict(self) -> Dict[str, Any]:
        """작업 정보를 딕셔너리로 변환"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            ),
            "result": self.result,
            "error": self.error
        }

class AsyncTaskManager(LoggerMixin):
    """비동기 작업 관리자"""

    def __init__(self):
        self.tasks: Dict[str, AsyncTask] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.worker_count = 3
        self.workers: List[asyncio.Task] = []

    def create_task(
        self,
        task_type: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300
    ) -> str:
        """새 작업 생성"""
        task_id = str(uuid.uuid4())

        task = AsyncTask(
            task_id=task_id,
            task_type=task_type,
            func=func,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout
        )

        self.tasks[task_id] = task

        # 큐에 작업 추가
        self.task_queue.put_nowait(task)

        self.logger.info(f"새 작업 생성: {task_id} ({task_type})")
        return task_id

    async def start(self):
        """작업 처리 워커 시작"""
        self.logger.info(f"비동기 작업 관리자 시작 (워커 수: {self.worker_count})")

        # 워커 태스크 생성
        self.workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.worker_count)
        ]

        # 모든 워커가 완료될 때까지 대기
        await asyncio.gather(*self.workers)

    async def _worker(self, worker_name: str):
        """작업 처리 워커"""
        self.logger.info(f"워커 시작: {worker_name}")

        while True:
            try:
                # 큐에서 작업 가져오기 (타임아웃 설정)
                try:
                    task = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # 큐가 비어있으면 계속 대기
                    continue

                self.logger.info(f"작업 실행 시작: {task.task_id} ({worker_name})")

                try:
                    await task.execute()
                except Exception as e:
                    self.logger.error(f"작업 실행 실패: {task.task_id} - {e}")
                finally:
                    # 작업 완료 처리
                    self.task_queue.task_done()

            except Exception as e:
                self.logger.error(f"워커 에러: {worker_name} - {e}")
                await asyncio.sleep(1)  # 잠시 대기 후 재시도

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """작업 조회"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, AsyncTask]:
        """모든 작업 조회"""
        return self.tasks.copy()

    def get_tasks_by_status(self, status: TaskStatus) -> Dict[str, AsyncTask]:
        """상태별 작업 조회"""
        return {
            task_id: task
            for task_id, task in self.tasks.items()
            if task.status == status
        }

    def cancel_task(self, task_id: str) -> bool:
        """작업 취소"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            return True

        return False

    def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """완료된 작업 정리"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

        completed_task_ids = [
            task_id for task_id, task in self.tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            and task.completed_at and task.completed_at < cutoff_time
        ]

        for task_id in completed_task_ids:
            del self.tasks[task_id]

        if completed_task_ids:
            self.logger.info(f"완료된 작업 정리: {len(completed_task_ids)}개 작업 삭제")

        return len(completed_task_ids)

# 전역 작업 관리자 인스턴스
task_manager = AsyncTaskManager()

def create_bulk_product_task(
    products_data: List[Dict[str, Any]],
    supplier_id: int,
    supplier_account_id: int
) -> str:
    """대량 상품 등록 작업 생성"""
    async def bulk_create_products():
        from app.services.product_service import ProductSyncService
        from app.models.database import async_session

        async with async_session() as db:
            sync_service = ProductSyncService(db)

            # 상품 데이터에 공급사 정보 추가
            for product_data in products_data:
                product_data.setdefault('supplier_id', supplier_id)
                product_data.setdefault('supplier_account_id', supplier_account_id)

            result = await sync_service.bulk_create_products(products_data)
            return result

    return task_manager.create_task(
        task_type="bulk_product_create",
        func=bulk_create_products,
        args=(),
        kwargs={},
        max_retries=3,
        timeout=600  # 10분 타임아웃
    )

def create_product_collection_task(
    supplier_id: int,
    supplier_account_id: Optional[int] = None,
    item_keys: Optional[List[str]] = None,
    force_sync: bool = False
) -> str:
    """상품 수집 작업 생성"""
    async def collect_products():
        from app.services.product_service import ProductService
        from app.models.database import async_session

        async with async_session() as db:
            product_service = ProductService(db)
            result = await product_service.collect_products(
                supplier_id=supplier_id,
                supplier_account_id=supplier_account_id,
                item_keys=item_keys,
                force_sync=force_sync
            )
            return result

    return task_manager.create_task(
        task_type="product_collection",
        func=collect_products,
        args=(),
        kwargs={},
        max_retries=3,
        timeout=300  # 5분 타임아웃
    )
