"""WebSocket 실시간 모니터링 라우트"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime

router = APIRouter()

# 연결된 클라이언트들
connected_clients: List[WebSocket] = []

@router.websocket("/ws/sync-status")
async def websocket_sync_status(websocket: WebSocket):
    """실시간 동기화 상태 WebSocket"""
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        while True:
            # 클라이언트로부터 메시지 수신 (필요시)
            data = await websocket.receive_text()

            # 현재 동기화 상태 정보 전송
            sync_status = {
                "type": "sync_status",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "active_syncs": 0,
                    "completed_syncs": 0,
                    "failed_syncs": 0,
                    "total_products": 0,
                    "total_orders": 0
                }
            }

            await websocket.send_text(json.dumps(sync_status))

            # 5초마다 상태 업데이트
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        print(f"WebSocket 오류: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)

@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """알림 WebSocket"""
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        while True:
            # 알림 메시지 전송
            notification = {
                "type": "notification",
                "timestamp": datetime.now().isoformat(),
                "title": "테스트 알림",
                "message": "시스템이 정상 작동 중입니다.",
                "type": "info"
            }

            await websocket.send_text(json.dumps(notification))

            # 10초마다 알림
            await asyncio.sleep(10)

    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        print(f"WebSocket 알림 오류: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)
