"""
상품 수집 진행 상황 추적을 위한 WebSocket 관리자
"""
import asyncio
import json
from typing import Dict, Set, Optional, Any
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from app.core.logging import get_logger

logger = get_logger(__name__)

class ProgressTracker:
    """상품 수집 진행 상황 추적기"""
    
    def __init__(self):
        # 연결된 WebSocket 클라이언트들
        self.active_connections: Set[WebSocket] = set()
        # 진행 상황 데이터
        self.progress_data: Dict[str, Dict[str, Any]] = {}
        # 작업 상태
        self.running_tasks: Dict[str, bool] = {}
    
    async def connect(self, websocket: WebSocket):
        """WebSocket 연결"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 연결됨. 총 연결 수: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결 해제"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 연결 해제됨. 총 연결 수: {len(self.active_connections)}")
    
    async def broadcast_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """모든 연결된 클라이언트에게 진행 상황 브로드캐스트"""
        self.progress_data[task_id] = progress_data
        
        message = {
            "type": "progress_update",
            "task_id": task_id,
            "data": progress_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # 연결이 끊어진 클라이언트들 제거
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"WebSocket 메시지 전송 실패: {e}")
                disconnected.add(websocket)
        
        # 연결이 끊어진 클라이언트들 제거
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def broadcast_completion(self, task_id: str, result: Dict[str, Any]):
        """작업 완료 브로드캐스트"""
        message = {
            "type": "task_completed",
            "task_id": task_id,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"WebSocket 완료 메시지 전송 실패: {e}")
                disconnected.add(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket)
        
        # 작업 완료 후 정리
        self.running_tasks.pop(task_id, None)
        self.progress_data.pop(task_id, None)
    
    async def broadcast_error(self, task_id: str, error: str):
        """에러 브로드캐스트"""
        message = {
            "type": "task_error",
            "task_id": task_id,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"WebSocket 에러 메시지 전송 실패: {e}")
                disconnected.add(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket)
        
        # 에러 후 정리
        self.running_tasks.pop(task_id, None)
        self.progress_data.pop(task_id, None)
    
    def start_task(self, task_id: str, total_items: int = 0):
        """작업 시작"""
        self.running_tasks[task_id] = True
        self.progress_data[task_id] = {
            "status": "started",
            "current": 0,
            "total": total_items,
            "percentage": 0,
            "message": "작업을 시작합니다...",
            "started_at": datetime.now().isoformat(),
            "estimated_completion": None
        }
    
    def update_progress(
        self, 
        task_id: str, 
        current: int, 
        message: str = "", 
        items_processed: Optional[Dict[str, int]] = None
    ):
        """진행 상황 업데이트"""
        if task_id not in self.progress_data:
            return
        
        progress = self.progress_data[task_id]
        total = progress.get("total", 1)
        
        progress.update({
            "current": current,
            "percentage": min(100, int((current / total) * 100)) if total > 0 else 0,
            "message": message or f"{current}/{total} 처리 중...",
            "updated_at": datetime.now().isoformat()
        })
        
        if items_processed:
            progress["items_processed"] = items_processed
        
        # 예상 완료 시간 계산
        if current > 0 and total > 0:
            started_at = datetime.fromisoformat(progress["started_at"])
            elapsed = (datetime.now() - started_at).total_seconds()
            rate = current / elapsed if elapsed > 0 else 0
            remaining = (total - current) / rate if rate > 0 else 0
            progress["estimated_completion"] = (
                datetime.now() + timedelta(seconds=remaining)
            ).isoformat()
    
    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """작업 완료"""
        if task_id in self.progress_data:
            self.progress_data[task_id].update({
                "status": "completed",
                "percentage": 100,
                "message": "작업이 완료되었습니다.",
                "completed_at": datetime.now().isoformat()
            })
    
    def fail_task(self, task_id: str, error: str):
        """작업 실패"""
        if task_id in self.progress_data:
            self.progress_data[task_id].update({
                "status": "failed",
                "message": f"작업 실패: {error}",
                "failed_at": datetime.now().isoformat()
            })
    
    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """진행 상황 조회"""
        return self.progress_data.get(task_id)
    
    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """모든 진행 상황 조회"""
        return self.progress_data.copy()
    
    def is_task_running(self, task_id: str) -> bool:
        """작업 실행 중 여부"""
        return self.running_tasks.get(task_id, False)

# 전역 진행 상황 추적기 인스턴스
progress_tracker = ProgressTracker()

# 진행 상황 업데이트 헬퍼 함수들
async def update_collection_progress(
    task_id: str,
    current: int,
    total: int,
    message: str = "",
    items_processed: Optional[Dict[str, int]] = None
):
    """상품 수집 진행 상황 업데이트"""
    progress_tracker.update_progress(task_id, current, message, items_processed)
    await progress_tracker.broadcast_progress(task_id, progress_tracker.get_progress(task_id))

async def complete_collection_task(task_id: str, result: Dict[str, Any]):
    """상품 수집 작업 완료"""
    progress_tracker.complete_task(task_id, result)
    await progress_tracker.broadcast_completion(task_id, result)

async def fail_collection_task(task_id: str, error: str):
    """상품 수집 작업 실패"""
    progress_tracker.fail_task(task_id, error)
    await progress_tracker.broadcast_error(task_id, error)
