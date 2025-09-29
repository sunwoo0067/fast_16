"""
진행 상황 추적 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

from app.models.database import get_db
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# 메모리 기반 진행 상황 저장소 (실제 운영에서는 Redis 등 사용)
progress_store: Dict[str, Dict[str, Any]] = {}

@router.post("/progress/{task_id}")
async def update_progress(
    task_id: str,
    progress_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """진행 상황 업데이트"""
    try:
        progress_data["updated_at"] = datetime.now().isoformat()
        progress_store[task_id] = progress_data
        
        logger.info(f"진행 상황 업데이트: {task_id} - {progress_data.get('status', 'unknown')}")
        
        return {"message": "진행 상황이 업데이트되었습니다", "task_id": task_id}
        
    except Exception as e:
        logger.error(f"진행 상황 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/{task_id}")
async def get_progress(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 작업의 진행 상황 조회"""
    try:
        if task_id not in progress_store:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        progress_data = progress_store[task_id]
        
        # 오래된 작업 정리 (1시간 이상)
        updated_at = datetime.fromisoformat(progress_data.get("updated_at", ""))
        if datetime.now() - updated_at > timedelta(hours=1):
            del progress_store[task_id]
            raise HTTPException(status_code=404, detail="작업이 만료되었습니다")
        
        return {
            "task_id": task_id,
            "progress": progress_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"진행 상황 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress")
async def get_all_progress(
    db: AsyncSession = Depends(get_db)
):
    """모든 작업의 진행 상황 조회"""
    try:
        # 오래된 작업 정리
        current_time = datetime.now()
        expired_tasks = []
        
        for task_id, progress_data in progress_store.items():
            updated_at = datetime.fromisoformat(progress_data.get("updated_at", ""))
            if current_time - updated_at > timedelta(hours=1):
                expired_tasks.append(task_id)
        
        for task_id in expired_tasks:
            del progress_store[task_id]
        
        return {
            "tasks": progress_store,
            "active_connections": len(progress_store)
        }
        
    except Exception as e:
        logger.error(f"전체 진행 상황 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/progress/{task_id}")
async def clear_progress(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """작업 완료 후 진행 상황 데이터 삭제"""
    try:
        if task_id in progress_store:
            del progress_store[task_id]
            logger.info(f"진행 상황 데이터 삭제: {task_id}")
        
        return {"message": "진행 상황 데이터가 삭제되었습니다", "task_id": task_id}
        
    except Exception as e:
        logger.error(f"진행 상황 데이터 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
