#!/usr/bin/env python3
"""
쿠팡 마켓플레이스 설정 스크립트
"""

import asyncio
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import create_coupang_supplier

async def main():
    """쿠팡 공급사 및 계정 생성"""
    print("쿠팡 마켓플레이스 설정을 시작합니다...")

    try:
        supplier_id, account_id = await create_coupang_supplier()
        print("✅ 쿠팡 마켓플레이스 설정 완료!")
        print(f"   공급사 ID: {supplier_id}")
        print(f"   계정 ID: {account_id}")
        print(f"   업체코드: A01282691")
        print(f"   Access Key: a825d408-a53d-4234-bdaa-be67acd67e5d")
        print(f"   Secret Key: 856d45fae108cbf8029eaa0544bcbeed2a21f9d4")

        # 연결 테스트
        print("\n🔧 쿠팡 API 연결 테스트를 시작합니다...")
        await test_coupang_connection(supplier_id)

    except Exception as e:
        print(f"❌ 설정 중 오류 발생: {e}")
        sys.exit(1)

async def test_coupang_connection(supplier_id: int):
    """쿠팡 API 연결 테스트"""
    try:
        from services import CoupangService
        from database import async_session

        async with async_session() as session:
            service = CoupangService(session)
            result = await service.test_coupang_connection(supplier_id)

            if result["status"] == "success":
                print("✅ 쿠팡 API 연결 테스트 성공!")
                print(f"   메시지: {result['message']}")
                if "data" in result:
                    print(f"   응답 데이터: {result['data']}")
            else:
                print("❌ 쿠팡 API 연결 테스트 실패!")
                print(f"   오류 메시지: {result['message']}")

    except Exception as e:
        print(f"❌ 연결 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
