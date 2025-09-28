#!/usr/bin/env python3
"""
OwnerClan 실제 상품 데이터 수집 스크립트
"""

import asyncio
import sys
import os
from typing import Optional

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import async_session
from app.services.ownerclan_collector import OwnerClanCollector
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)

async def collect_ownerclan_products(
    supplier_account_id: int,
    limit: int = 50,
    dry_run: bool = False
):
    """OwnerClan 상품 데이터 수집"""
    print(f"[INFO] OwnerClan 상품 데이터 수집 시작 (계정 ID: {supplier_account_id}, 수량: {limit})")

    async with async_session() as session:
        collector = OwnerClanCollector(session)

        if dry_run:
            print("[INFO] Dry run 모드 - 실제 저장 없이 데이터 확인만 수행")
            # 실제 수집 로직은 같지만 저장은 건너뜀
            result = await collector.collect_products(supplier_account_id, limit)
        else:
            result = await collector.collect_products(supplier_account_id, limit)

        if result["success"]:
            print("[SUCCESS] 수집 완료!")
            print(f"   수집된 상품: {result['collected']}개")
            print(f"   저장된 상품: {result['saved']}개")
            print(f"   계정 ID: {result['supplier_account_id']}")

            # 통계 조회
            stats_result = await collector.get_collection_stats(supplier_account_id)
            if stats_result["success"]:
                stats = stats_result["stats"]
                print("[STATS] 현재 통계:")
                print(f"   총 상품: {stats['total_products']}개")
                print(f"   활성 상품: {stats['active_products']}개")
                print(f"   동기화된 상품: {stats['synced_products']}개")
                if stats['last_sync']:
                    print(f"   마지막 동기화: {stats['last_sync']}")

        else:
            print(f"[ERROR] 수집 실패: {result['error']}")
            return False

    return True

async def main():
    """메인 함수"""
    print("OwnerClan 상품 데이터 수집기")
    print("=" * 50)

    # OwnerClan 공급사 계정 ID 확인
    async with async_session() as session:
        from sqlalchemy import select, text
        from app.models.database import Supplier, SupplierAccount

        # OwnerClan 공급사 계정 조회
        result = await session.execute(text("""
            SELECT sa.id, sa.account_id, s.name
            FROM supplier_accounts sa
            JOIN suppliers s ON sa.supplier_id = s.id
            WHERE s.name LIKE '%오너클랜%'
            AND sa.is_active = true
        """))

        accounts = result.fetchall()

        if not accounts:
            print("[ERROR] OwnerClan 공급사 계정을 찾을 수 없습니다.")
            print("   먼저 OwnerClan 공급사를 설정해주세요.")
            return

        print("사용 가능한 OwnerClan 계정:")
        for i, account in enumerate(accounts, 1):
            print(f"  {i}. 계정 ID: {account[0]}, 사용자: {account[1]}, 공급사: {account[2]}")

        # 계정 선택
        while True:
            try:
                choice = input("\n사용할 계정 번호를 선택하세요 (1-{}): ".format(len(accounts)))
                choice = int(choice)
                if 1 <= choice <= len(accounts):
                    selected_account = accounts[choice - 1]
                    supplier_account_id = selected_account[0]
                    break
                else:
                    print(f"1-{len(accounts)} 범위의 숫자를 입력해주세요.")
            except ValueError:
                print("숫자를 입력해주세요.")

        # 수집할 상품 수 입력
        while True:
            try:
                limit_input = input("수집할 상품 수를 입력하세요 (기본 50개): ").strip()
                limit = int(limit_input) if limit_input else 50
                if 1 <= limit <= 500:
                    break
                else:
                    print("1-500 범위의 숫자를 입력해주세요.")
            except ValueError:
                print("숫자를 입력해주세요.")

        # Dry run 여부 확인
        dry_run_input = input("Dry run 모드로 실행하시겠습니까? (y/N): ").strip().lower()
        dry_run = dry_run_input == 'y'

        print(f"\n선택된 계정 ID: {supplier_account_id}")
        print(f"수집할 상품 수: {limit}")
        print(f"Dry run 모드: {'예' if dry_run else '아니오'}")
        print("-" * 50)

        # 수집 실행
        success = await collect_ownerclan_products(supplier_account_id, limit, dry_run)

        if success:
            print("\n[SUCCESS] OwnerClan 상품 데이터 수집이 완료되었습니다!")
            if not dry_run:
                print("[INFO] 수집된 데이터가 데이터베이스에 저장되었습니다.")
            else:
                print("[INFO] 실제 저장 없이 데이터 확인만 수행되었습니다.")
        else:
            print("\n[ERROR] 상품 데이터 수집에 실패했습니다.")
            print("   로그를 확인하고 API 연결 상태를 점검해주세요.")

if __name__ == "__main__":
    # 로깅 설정
    setup_logging()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[WARNING] 사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류가 발생했습니다: {e}")
        logger.error(f"OwnerClan 수집 스크립트 오류: {e}")
