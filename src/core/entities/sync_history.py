"""동기화 이력 도메인 엔티티"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class SyncType(Enum):
    """동기화 타입"""
    INGEST = "ingest"        # 공급사에서 데이터 수집
    NORMALIZE = "normalize"  # 표준화
    UPLOAD = "upload"        # 마켓 업로드
    PRICE_UPDATE = "price_update"  # 가격 업데이트
    STOCK_UPDATE = "stock_update"  # 재고 업데이트
    VALIDATE = "validate"    # 검증


class SyncStatus(Enum):
    """동기화 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SyncResult:
    """동기화 결과 정보"""
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    errors: Dict[str, str] = field(default_factory=dict)

    def add_success(self, item_id: str) -> None:
        """성공 추가"""
        self.success_count += 1
        self.total_count += 1

    def add_failure(self, item_id: str, error: str) -> None:
        """실패 추가"""
        self.failure_count += 1
        self.total_count += 1
        self.errors[item_id] = error

    def is_successful(self) -> bool:
        """전체 성공 여부"""
        return self.failure_count == 0 and self.total_count > 0

    def get_success_rate(self) -> float:
        """성공률 계산"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


@dataclass
class SyncHistory:
    """동기화 이력 도메인 엔티티"""
    id: str
    sync_type: SyncType
    status: SyncStatus = SyncStatus.PENDING
    item_id: Optional[str] = None  # 특정 상품 동기화시
    supplier_id: Optional[str] = None  # 특정 공급사 동기화시
    market_type: Optional[str] = None  # 특정 마켓 동기화시
    result: Optional[SyncResult] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    def start(self) -> None:
        """동기화 시작"""
        self.status = SyncStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, result: SyncResult, error_message: Optional[str] = None) -> None:
        """동기화 완료"""
        self.status = SyncStatus.SUCCESS if result.is_successful() else SyncStatus.FAILED
        self.result = result
        self.error_message = error_message
        self.completed_at = datetime.now()

        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def fail(self, error_message: str) -> None:
        """동기화 실패"""
        self.status = SyncStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now()

        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def can_retry(self) -> bool:
        """재시도 가능 여부"""
        return self.retry_count < self.max_retries and self.status == SyncStatus.FAILED

    def increment_retry(self) -> None:
        """재시도 횟수 증가"""
        self.retry_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (직렬화용)"""
        return {
            'id': self.id,
            'item_id': self.item_id,
            'supplier_id': self.supplier_id,
            'market_type': self.market_type,
            'sync_type': self.sync_type.value,
            'status': self.status.value,
            'result': {
                'success_count': self.result.success_count,
                'failure_count': self.result.failure_count,
                'total_count': self.result.total_count,
                'success_rate': self.result.get_success_rate(),
                'errors': self.result.errors
            } if self.result else None,
            'details': self.details,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'can_retry': self.can_retry()
        }
