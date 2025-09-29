"""
WebSocket 엔드포인트 - 실시간 진행 상황 추적
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import json
import asyncio

from app.websocket.progress_tracker import progress_tracker
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.websocket("/progress")
async def websocket_progress_endpoint(websocket: WebSocket, client_id: str = "default_client"):
    """상품 수집 진행 상황 WebSocket 엔드포인트"""
    await progress_tracker.connect(websocket)
    
    try:
        # 연결 시 현재 진행 상황 전송
        # progress_manager는 현재 진행 상황을 별도로 저장하지 않으므로 생략
        
        # 클라이언트 메시지 대기
        while True:
            try:
                # 클라이언트로부터 메시지 수신 (ping/pong 등)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    }))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket 메시지 처리 오류: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket 연결 오류: {e}")
    finally:
        progress_tracker.disconnect(websocket)

@router.get("/progress/{task_id}")
async def get_progress(task_id: str) -> Dict[str, Any]:
    """특정 작업의 진행 상황 조회"""
    progress = progress_tracker.get_progress(task_id)
    if not progress:
        return {"error": "작업을 찾을 수 없습니다"}
    
    return {
        "task_id": task_id,
        "progress": progress
    }

@router.get("/progress")
async def get_all_progress() -> Dict[str, Any]:
    """모든 작업의 진행 상황 조회"""
    return {
        "tasks": progress_tracker.get_all_progress(),
        "active_connections": len(progress_tracker.active_connections)
    }
