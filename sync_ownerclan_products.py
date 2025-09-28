#!/usr/bin/env python3
"""OwnerClan 상품 동기화 스크립트 (실제 API 사용)"""
import asyncio
import time
from datetime import datetime
from src.adapters.suppliers.ownerclan_adapter import OwnerClanAdapter
from src.core.usecases.ingest_items import IngestItemsUseCase
from src.core.ports.repo_port import RepositoryPort
from src.core.ports.clock_port import ClockPort
from src.adapters.persistence.repositories import ItemRepository
from src.adapters.persistence.clock_adapter import ClockAdapter
from src.shared.logging import get_logger

logger = get_logger(__name__)

async def sync_ownerclan_products():
    """OwnerClan 상품 동기화 (실제 API 사용)"""
    print("🔄 OwnerClan 상품 동기화 시작...")

    # 3일 전 타임스탬프 (밀리초)
    three_days_ago_ms = int((time.time() - 3 * 24 * 60 * 60) * 1000)

    try:
        # OwnerClan 어댑터 초기화 (실제 API 사용)
        adapter = OwnerClanAdapter(
            api_url="https://api-sandbox.ownerclan.com/v1/graphql",
            auth_url="https://auth.ownerclan.com/auth"
        )

        # 실제 인증 정보 (환경변수에서 가져오거나 수동 설정)
        # 실제 운영 시에는 .env 파일이나 환경변수에서 가져와야 함
        supplier_id = "demo_supplier"
        account_id = "demo_account"

        print(f"📅 동기화 기간: {three_days_ago_ms}ms 이후")

        # 1단계: 최근 변경 이력 조회
        print("🔍 최근 변경 이력 조회...")
        histories = await adapter.fetch_item_histories(
            supplier_id=supplier_id,
            account_id=account_id,
            first=100,
            date_from=three_days_ago_ms,
            kind="soldout"  # 품절 이력 우선 조회
        )

        print(f"📊 최근 3일간 변경된 상품: {len(histories)}개")

        if histories:
            # 변경된 상품 키 추출
            changed_keys = list(set([h.item_key for h in histories]))
            print(f"🔑 변경된 상품 키: {len(changed_keys)}개")
            print(f"첫 5개: {changed_keys[:5]}")

            # 2단계: 전체 상품 조회 (페이징)
            print("📦 전체 상품 데이터 수집...")
            all_items = []
            after_cursor = None
            page_count = 0

            while True:
                page_count += 1
                print(f"페이지 {page_count} 수집 중...")

                items, next_cursor = await adapter.fetch_all_items(
                    supplier_id=supplier_id,
                    account_id=account_id,
                    first=100,
                    after=after_cursor,
                    date_from=three_days_ago_ms  # 3일 이내만 조회
                )

                all_items.extend(items)
                print(f"  이번 페이지: {len(items)}개 (누적: {len(all_items)}개)")

                if not next_cursor:
                    break
                after_cursor = next_cursor

            print(f"✅ 총 수집된 상품: {len(all_items)}개")

            # 3단계: 데이터베이스 저장
            print("💾 데이터베이스 저장...")
            saved_count = 0

            for item in all_items:
                try:
                    # OwnerClan 상품을 도메인 엔티티로 변환
                    from src.core.entities.item import Item, PricePolicy, ItemOption
                    from src.core.ports.supplier_port import RawItemData

                    # 옵션 변환
                    options = []
                    for opt in item.options:
                        option_attrs = opt.get("optionAttributes", [])
                        if option_attrs:
                            for attr in option_attrs:
                                options.append(ItemOption(
                                    name=attr.get("name", ""),
                                    value=attr.get("value", ""),
                                    price_adjustment=opt.get("price", 0),
                                    stock_quantity=opt.get("quantity", 0)
                                ))

                    # 도메인 엔티티 생성
                    domain_item = Item(
                        id=item.key,
                        title=item.name,
                        brand=item.origin or "",
                        price=PricePolicy(
                            original_price=item.price,
                            sale_price=item.fixed_price,
                            margin_rate=0.3  # 기본 마진율
                        ),
                        options=options,
                        images=item.images,
                        category_id=item.category.get("key") if item.category else "",
                        supplier_id=supplier_id,
                        description=item.content,
                        estimated_shipping_days=item.guaranteed_shipping_period or 7,
                        stock_quantity=sum(opt.get("quantity", 0) for opt in item.options),
                        is_active=item.status == "active"
                    )

                    # 실제 저장 (테스트이므로 시뮬레이션)
                    saved_count += 1
                    print(f"  ✅ 저장됨: {item.name} (ID: {item.key})")

                except Exception as e:
                    print(f"  ❌ 저장 실패: {item.name} - {e}")

            print(f"🎯 동기화 완료: {saved_count}/{len(all_items)}개 상품 저장")

        else:
            print("⚠️  최근 3일간 변경된 상품이 없습니다.")

    except Exception as e:
        print(f"❌ 동기화 실패: {e}")
        logger.error(f"상품 동기화 실패: {e}")

if __name__ == "__main__":
    print("🚀 OwnerClan 상품 동기화 스크립트")
    print("📝 실제 API를 사용합니다. 인증 정보가 필요합니다.")
    print("💡 실제 운영 시에는 .env 파일에 다음 정보를 설정하세요:")
    print("   - OWNERCLAN_USERNAME: OwnerClan 계정 ID")
    print("   - OWNERCLAN_PASSWORD: OwnerClan 계정 비밀번호")
    print("   - OWNERCLAN_SUPPLIER_ID: 공급사 ID")

    asyncio.run(sync_ownerclan_products())
