#!/usr/bin/env python3
"""
쿠팡 API 연결 테스트 스크립트
"""

import asyncio
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import CoupangService
from database import async_session
from sqlalchemy import select, and_
from database import SupplierAccount

async def test_coupang_api():
    """쿠팡 API 연결 테스트"""
    print("쿠팡 API 연결 테스트를 시작합니다...")

    async with async_session() as session:
        try:
            # 쿠팡 마켓플레이스 계정 찾기
            result = await session.execute(
                select(SupplierAccount).where(
                    and_(
                        SupplierAccount.supplier_id == 2,  # 쿠팡 마켓플레이스 ID
                        SupplierAccount.is_active == True
                    )
                )
            )
            account = result.scalar_one_or_none()

            if not account:
                print("쿠팡 마켓플레이스 계정을 찾을 수 없습니다.")
                return

            print(f"계정 발견: ID {account.id}, 공급사ID: {account.supplier_id}")

            # 쿠팡 인증 정보 확인
            if hasattr(account, 'coupang_access_key') and account.coupang_access_key:
                print("쿠팡 인증 정보가 설정되어 있습니다.")
                print(f"  벤더ID: {account.coupang_vendor_id}")
                print(f"  Access Key: {account.coupang_access_key[:20]}...")
                print(f"  Secret Key: {account.coupang_secret_key[:20]}...")
            else:
                print("쿠팡 인증 정보가 설정되지 않았습니다.")
                return

            # CoupangService 생성 및 테스트
            coupang_service = CoupangService(session)

            print("\n연결 테스트를 시작합니다...")
            result = await coupang_service.test_coupang_connection(2)

            if result["status"] == "success":
                print("✅ 쿠팡 API 연결 테스트 성공!")
                print(f"  메시지: {result['message']}")
                if "data" in result:
                    print(f"  응답 데이터: {result['data']}")
            else:
                print("❌ 쿠팡 API 연결 테스트 실패!")
                print(f"  오류 메시지: {result['message']}")

        except Exception as e:
            print(f"테스트 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_coupang_api())
