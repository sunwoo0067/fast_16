#!/usr/bin/env python3
"""
현재 상태 확인 스크립트
"""

import asyncio
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import async_session, Supplier, SupplierAccount
from sqlalchemy import select, and_

async def check_current_status():
    """현재 데이터베이스 상태 확인"""
    print("현재 데이터베이스 상태를 확인합니다...")

    async with async_session() as session:
        try:
            # 모든 공급사 조회
            result = await session.execute(select(Supplier).where(Supplier.is_active == True))
            suppliers = result.scalars().all()

            print(f"\n현재 활성화된 공급사 수: {len(suppliers)}")
            for supplier in suppliers:
                print(f"  - ID: {supplier.id}, 이름: {supplier.name}")

            # 모든 계정 조회
            result = await session.execute(select(SupplierAccount).where(SupplierAccount.is_active == True))
            accounts = result.scalars().all()

            print(f"\n현재 활성화된 계정 수: {len(accounts)}")
            for account in accounts:
                print(f"  - ID: {account.id}, 공급사ID: {account.supplier_id}, 계정ID: {account.account_id}")
                if hasattr(account, 'coupang_access_key') and account.coupang_access_key:
                    print(f"    쿠팡 인증 정보: 설정됨 (벤더ID: {account.coupang_vendor_id})")
                else:
                    print(f"    쿠팡 인증 정보: 미설정")

            # 쿠팡 마켓플레이스 찾기
            coupang_supplier = None
            for supplier in suppliers:
                if "쿠팡" in supplier.name:
                    coupang_supplier = supplier
                    break

            if coupang_supplier:
                print(f"\n쿠팡 마켓플레이스 발견: ID {coupang_supplier.id}")
            else:
                print("\n쿠팡 마켓플레이스가 없습니다.")

        except Exception as e:
            print(f"상태 확인 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(check_current_status())
