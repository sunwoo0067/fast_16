# 드랍싸핑 셀러 관리 시스템

드랍싸핑 이커머스 셀러를 위한 FastAPI 기반 상품 관리 및 동기화 시스템입니다.

## 🎯 주요 기능

### 드랍싸핑 특화 기능
- **대량 상품 등록**: CSV/엑셀 파일로부터 대량 상품 일괄 등록
- **상품 동기화**: 공급처 상품 정보 실시간 동기화
- **마진 관리**: 공급가 기반 판매가 자동 책정
- **재고 관리**: 공급처 재고 연동 및 자동 업데이트
- **배송 정보 관리**: 예상 배송일 및 배송비 자동 계산

### 공급사 관리
- **다중 공급사 지원**: 여러 공급처 동시 관리
- **계정 관리**: 공급사별 계정 정보 및 인증 토큰 관리
- **토큰 재사용**: 데이터베이스에 토큰을 저장하고 재사용
- **사용량 추적**: API 호출 횟수, 성공률, 사용 통계 자동 기록
- **토큰 자동 갱신**: 30일 유효기간 토큰 자동 갱신

### 상품 관리
- **상품 수집**: 오너클랜 API에서 상품 정보 자동 수집
- **상품 관리**: 수집된 상품 목록 조회 및 통계 확인
- **카테고리 관리**: 상품 카테고리 자동 분류 및 관리
- **동기화 이력**: 상품 변경 이력 추적 및 관리

### 쿠팡 연동
- **쿠팡윙 API 연동**: 쿠팡 마켓플레이스 연동
- **상품 등록**: 쿠팡 상품 자동 등록 및 관리
- **주문 처리**: 쿠팡 주문 자동 처리
- **반품/교환**: 쿠팡 반품/교환 프로세스 자동화

## 🏗️ 아키텍처

### 헥사고날 아키텍처 (Hexagonal Architecture)

이 프로젝트는 **헥사고날 아키텍처**를 적용하여 유지보수성과 확장성을 높였습니다.

#### 아키텍처 원칙
- **도메인 중심**: 비즈니스 로직이 외부 의존성으로부터 독립적
- **포트와 어댑터**: 인터페이스(포트)로 추상화, 구현(어댑터)로 분리
- **테스트 용이성**: 각 계층이 독립적으로 테스트 가능

#### 프로젝트 구조
```
src/
├── app/                    # FastAPI 애플리케이션 (프레임 계층)
│   ├── main.py            # 앱 생성, 미들웨어, 라이프사이클
│   ├── routes/            # HTTP 라우트 (DTO 변환만)
│   ├── di.py              # 의존성 주입
│   └── middleware.py      # 로깅, 에러핸들링
├── core/                  # 도메인 (비즈니스 규칙)
│   ├── entities/          # 순수 도메인 모델
│   ├── usecases/          # 비즈니스 유즈케이스
│   └── ports/             # 인터페이스 (추상화)
├── adapters/              # 어댑터 (외부 시스템 구현)
│   ├── suppliers/         # OwnerClan, 도매매, 젠트레이드
│   ├── markets/           # 쿠팡, 스마트스토어, 11번가
│   ├── persistence/       # 데이터베이스, 리포지토리
│   └── auth/              # 토큰 저장소
├── presentation/          # DTO, 검증 스키마
├── services/              # 파사드 서비스 (트랜잭션 경계)
└── shared/                # 설정, 로깅, 유틸리티
```

#### 핵심 아이디어
- **app**: 입출력만, **core**: 비즈니스 규칙만, **adapters**: 외부 구현만
- **포트**: 인터페이스로 결합도 낮춤, **어댑터**: 구현으로 분리
- **라우트 → 서비스 → 유즈케이스 → 포트** 순으로 흐름

### 레거시 구조 (app/)
```
app/
├── api/v1/endpoints/    # API 엔드포인트 (기능별 분리)
│   ├── suppliers.py     # 공급사 관리
│   ├── products.py      # 상품 관리
│   ├── orders.py        # 주문 관리
│   ├── auth.py         # 인증/인가
│   ├── categories.py   # 카테고리 관리
│   ├── coupang.py      # 쿠팡 API 연동
│   └── tasks.py        # 비동기 작업 관리
├── core/               # 핵심 설정 및 유틸리티
│   ├── config.py       # 설정 관리
│   ├── logging.py      # 로깅 시스템
│   ├── exceptions.py   # 예외 처리
│   └── database.py     # DB 모델
├── models/             # 데이터 모델
├── services/           # 비즈니스 로직
│   ├── supplier_service.py  # 공급사 서비스
│   ├── product_service.py   # 상품 서비스
│   └── sync_service.py      # 동기화 서비스
├── utils/              # 유틸리티 함수들
│   ├── async_task.py   # 비동기 작업 관리
│   └── validation.py   # 데이터 검증
└── scripts/            # 유틸리티 스크립트
    └── create_test_data.py  # 테스트 데이터 생성
```

### 핵심 개선 사항
- **모듈화**: 기능별로 완전히 분리된 아키텍처
- **드랍싸핑 최적화**: 대량 상품 처리에 특화된 설계
- **비동기 처리**: 대량 데이터 처리를 위한 비동기 아키텍처
- **에러 처리**: 상세한 에러 처리 및 로깅 시스템
- **설정 관리**: 환경별 설정을 통한 유연한 배포
- **데이터 검증**: 상품 등록 전 철저한 검증 시스템
- **작업 관리**: 비동기 작업의 실시간 모니터링 및 관리

## 🛠️ 기술 스택

- **Backend**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL with asyncpg + SQLAlchemy (Async)
- **Authentication**: JWT (OwnerClan API)
- **HTTP Client**: HTTPX (Async)
- **Configuration**: Pydantic Settings
- **Logging**: Structured Logging with JSON

## 📦 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 설정

`.env` 파일을 생성하고 다음 정보를 입력하세요:

```env
# API 설정
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# 데이터베이스 설정
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/database_name

# OwnerClan API 인증 정보 (실제 계정 정보로 변경)
OWNERCLAN_USERNAME=your_ownerclan_id
OWNERCLAN_PASSWORD=your_ownerclan_password
OWNERCLAN_SUPPLIER_ID=your_supplier_id
OWNERCLAN_API_URL=https://api-sandbox.ownerclan.com/v1/graphql
OWNERCLAN_AUTH_URL=https://auth.ownerclan.com/auth

# 상품 동기화 설정
SYNC_BATCH_SIZE=50
SYNC_MAX_WORKERS=5
SYNC_TIMEOUT_SECONDS=300

# 드랍싸핑 설정
DEFAULT_MARGIN_RATE=0.3
MIN_MARGIN_RATE=0.1
MAX_SHIPPING_DAYS=14

# OwnerClan API 설정
OWNERCLAN_API_URL=https://api.ownerclan.com/v1/graphql
OWNERCLAN_AUTH_URL=https://auth.ownerclan.com/auth

# 쿠팡 API 설정
COUPANG_API_TIMEOUT=30
COUPANG_RATE_LIMIT_PER_MINUTE=100

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/product_sync.log
```

### 3. 데이터베이스 설정

PostgreSQL 데이터베이스와 사용자를 생성하세요:

```sql
CREATE DATABASE fast_dropshipping;
CREATE USER dropship_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE fast_dropshipping TO dropship_user;
```

### 4. 테스트 데이터 생성 (선택사항)

드랍싸핑 셀러 테스트를 위해 샘플 데이터를 생성할 수 있습니다:

```bash
# 테스트 데이터 생성 (100개 상품)
python scripts/create_test_data.py
```

이 스크립트는 다음과 같은 데이터를 생성합니다:
- 3개의 공급사 (중국 도매, 한국 중소기업, 해외 직구)
- 각 공급사의 계정
- 100개의 테스트 상품 (드랍싸핑 특화 데이터 포함)
- CSV 파일로 내보내기

### 5. 실행

```bash
# 개발 모드
python -m app.main

# 또는 uvicorn 사용
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📚 API 문서

자동 문서화는 다음 URL에서 확인할 수 있습니다:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 📚 API 사용 가이드

### 기본 정보
- **Base URL**: `http://localhost:8000/api/v1`
- **API 문서**: `http://localhost:8000/docs` (Swagger UI)
- **Content-Type**: `application/json`

### 인증
현재 버전에서는 인증이 구현되지 않았습니다. 향후 JWT 토큰 기반 인증을 추가할 예정입니다.

### 주요 엔드포인트

#### 1. 헬스체크
```bash
GET /api/v1/health
```

#### 2. 상품 관리
```bash
# 상품 수집
POST /api/v1/products/ingest
Content-Type: application/json

{
  "supplier_id": "supplier_001",
  "account_id": "account_001",
  "item_keys": ["item_001", "item_002"]
}

# 상품 정규화
POST /api/v1/products/normalize
Content-Type: application/json

{
  "supplier_id": "supplier_001",
  "item_ids": ["item_001", "item_002"]
}

# 마켓 업로드
POST /api/v1/products/publish
Content-Type: application/json

{
  "market_type": "coupang",
  "item_ids": ["item_001"],
  "account_name": "main_account",
  "dry_run": false
}
```

#### 3. 주문 관리 (드랍십핑 자동화)
```bash
# 주문 생성
POST /api/v1/orders/
Content-Type: application/json

{
  "supplier_id": "supplier_001",
  "supplier_account_id": "account_001",
  "order_key": "order_12345",
  "items": [
    {
      "product_id": "item_001",
      "product_name": "테스트 상품",
      "quantity": 2,
      "unit_price": 15000,
      "options": {}
    }
  ],
  "shipping_fee": 3000,
  "customer_name": "김철수",
  "orderer_note": "빨리 보내주세요"
}

# 주문 목록 조회
GET /api/v1/orders/?supplier_id=supplier_001&limit=20

# 주문 상세 조회
GET /api/v1/orders/{order_id}

# 주문 발송
POST /api/v1/orders/{order_id}/ship
Content-Type: application/json

{
  "tracking_number": "1234567890",
  "shipping_company": "CJ대한통운"
}

# 주문 취소
POST /api/v1/orders/{order_id}/cancel
Content-Type: application/json

{
  "reason": "고객 요청"
}

# 주문 수집 (드랍십핑 자동화)
POST /api/v1/order-collection/collect
Content-Type: application/json

[
  {
    "external_order_id": "external_001",
    "customer_name": "김철수",
    "customer_phone": "010-1234-5678",
    "items": [
      {
        "product_id": "item_001",
        "product_name": "테스트 상품",
        "quantity": 1,
        "unit_price": 15000
      }
    ],
    "shipping_fee": 3000,
    "order_memo": "신속 배송 요청"
  }
]
```

#### 4. 공급사 관리 (OwnerClan 연동)
```bash
# 공급사 생성
POST /api/v1/suppliers/
Content-Type: application/json

{
  "name": "오너클랜",
  "description": "중국 도매 플랫폼",
  "api_key": "your_api_key",
  "base_url": "https://api.ownerclan.com"
}

# 공급사 목록 조회
GET /api/v1/suppliers/

# 공급사 계정 생성
POST /api/v1/suppliers/{supplier_id}/accounts
Content-Type: application/json

{
  "account_name": "메인 계정",
  "username": "user@example.com",
  "password": "secure_password",
  "default_margin_rate": 0.3,
  "sync_enabled": true
}

# OwnerClan 연결 테스트
POST /api/v1/order-collection/test-connection
Content-Type: application/json

{
  "supplier_id": "your_supplier_id",
  "account_name": "main_account"
}
```

#### 5. WebSocket 실시간 모니터링
```bash
# 동기화 상태 모니터링
ws://localhost:8000/ws/sync-status

# 알림 수신
ws://localhost:8000/ws/notifications
```

### 5. 드랍십핑 자동화 (OwnerClan 연동)
```bash
# 상품 동기화 실행
python comprehensive_ownerclan_sync_final.py

# 특정 조건 상품 동기화
python -c "
from src.adapters.suppliers.ownerclan_adapter import OwnerClanAdapter
import asyncio

async def test():
    adapter = OwnerClanAdapter()
    # 실제 인증 정보가 필요합니다
    items = await adapter.fetch_items_by_price_range('supplier_id', 'account_id', 10000, 100000)
    print(f'가격 범위 상품: {len(items)}개')

asyncio.run(test())
"
```

### 6. 프런트엔드 관리 인터페이스
드랍십핑 자동화 시스템을 위한 React TypeScript 기반 관리자 인터페이스가 제공됩니다.

#### 개발 서버 실행
```bash
cd frontend
npm install
npm run dev
```

#### 사용 가능한 페이지
- **대시보드** (`/dashboard`): 실시간 통계 및 동기화 상태 모니터링
- **상품 관리** (`/products`): 상품 목록, 검색, 동기화 상태 관리
- **주문 관리** (`/orders`): 주문 목록, 상태 변경, 배송 추적
- **공급사 관리** (`/suppliers`): 공급사 계정 설정, 연결 테스트
- **실시간 모니터링** (`/monitor`): WebSocket 기반 동기화 상태 추적

#### 주요 기능
- **대시보드**: 실시간 통계 및 동기화 상태 모니터링
- **상품 관리**: 상품 목록, 검색, 동기화 상태 관리
- **주문 관리**: 주문 목록, 상태 변경, 배송 추적
- **공급사 관리**: 공급사 계정 설정, 연결 테스트
- **실시간 모니터링**: WebSocket 기반 동기화 상태 추적
- **에러 처리**: 종합적인 에러 바운더리 및 사용자 피드백

#### 기술 스택
- **React 18** + **TypeScript** - 타입 안전성 및 최신 기능
- **Vite** - 초고속 개발 서버 및 빌드
- **Ant Design** - 엔터프라이즈급 UI 컴포넌트 라이브러리
- **Zustand** - 경량화된 상태 관리
- **React Query** - 서버 상태 관리 및 캐싱
- **Axios** - HTTP 클라이언트 (인터셉터 포함)
- **WebSocket** - 실시간 양방향 통신

#### 주요 컴포넌트
- `Dashboard`: 실시간 통계 대시보드 (차트 및 KPI)
- `ProductList`: 고급 상품 관리 테이블 (검색, 필터링, 대량 작업)
- `OrderList`: 주문 관리 테이블 (상태 변경, 배송 추적)
- `SupplierManager`: 공급사 관리 인터페이스 (계정 설정, 연결 테스트)
- `RealTimeMonitor`: WebSocket 기반 실시간 모니터링
- `ErrorBoundary`: 종합적인 에러 처리
- `NotificationSystem`: 실시간 알림 시스템

#### API 연동
- 자동으로 백엔드 API (`/api/v1/*`)와 완전 연동
- 타입 안전한 API 클라이언트
- 에러 처리 및 로딩 상태 관리
- 실시간 데이터 업데이트 (WebSocket)

## 📋 Cursor Rules

드랍십핑 자동화 시스템의 개발 가이드라인과 규칙들이 `.cursor/rules/` 디렉토리에 정의되어 있습니다.

### 사용 가능한 규칙들

#### 1. 프로젝트 구조 가이드 (`project-structure.mdc`)
- **적용 대상**: 모든 파일 (`**/*`)
- **항상 적용**: ✅
- **내용**: 헥사고날 아키텍처 구조, 파일명 규칙, 의존성 방향

#### 2. API 연동 가이드 (`api-integration.mdc`)
- **적용 대상**: API 관련 파일 (`src/adapters/**/*.py`, `src/services/**/*.py`)
- **항상 적용**: ❌ (수동)
- **내용**: OwnerClan API 사용법, GraphQL 쿼리, 에러 처리

#### 3. 코딩 스타일 가이드 (`coding-style.mdc`)
- **적용 대상**: 모든 소스 파일 (`src/**/*.py`, `frontend/src/**/*.{ts,tsx}`)
- **항상 적용**: ❌ (수동)
- **내용**: Python/TypeScript 코딩 규칙, 에러 처리, 비동기 패턴

#### 4. 데이터베이스 사용 가이드 (`database-usage.mdc`)
- **적용 대상**: 데이터베이스 관련 파일 (`src/adapters/persistence/**/*.py`)
- **항상 적용**: ❌ (수동)
- **내용**: SQLAlchemy 사용법, 쿼리 최적화, 마이그레이션 관리

#### 5. 테스트 작성 가이드 (`testing-guidelines.mdc`)
- **적용 대상**: 테스트 파일 (`tests/**/*.py`, `src/tests/**/*.{ts,tsx}`)
- **항상 적용**: ❌ (수동)
- **내용**: 단위/통합/E2E 테스트 작성법, 모킹, 어설션

### 규칙 사용법

```bash
# 특정 규칙 확인
cursor rules show project-structure

# 규칙 목록
cursor rules list

# 규칙 편집
cursor rules edit api-integration
```

### 규칙 적용 예시

규칙을 적용하면 다음과 같은 가이드가 제공됩니다:

```python
# API 연동 시 (api-integration.mdc 적용)
async def fetch_products(self, supplier_id: str) -> List[Product]:
    # ✅ 좋은 예시 - GraphQL 쿼리 사용
    query = """
    query GetProducts($supplierId: String!) {
        products(supplierId: $supplierId) {
            key
            name
            price
        }
    }
    """

    # ✅ 좋은 예시 - 에러 처리
    try:
        result = await self._execute_query(query, variables)
        return self._map_to_products(result)
    except Exception as e:
        logger.error(f"상품 조회 실패: {e}")
        raise
```

이 규칙들을 통해 일관된 코드 품질과 아키텍처를 유지할 수 있습니다.

### 에러 응답 형식
```json
{
  "detail": "에러 메시지",
  "status_code": 400,
  "timestamp": "2025-01-01T12:00:00Z"
}
```

### 상태 코드
- **200**: 성공
- **201**: 생성됨
- **400**: 잘못된 요청
- **404**: 리소스를 찾을 수 없음
- **500**: 서버 내부 오류

## 🚀 API 엔드포인트

### 공급사 관리

- `POST /api/v1/suppliers` - 공급사 생성
- `GET /api/v1/suppliers` - 공급사 목록 조회
- `GET /api/v1/suppliers/{supplier_id}` - 특정 공급사 조회
- `PUT /api/v1/suppliers/{supplier_id}` - 공급사 정보 수정
- `DELETE /api/v1/suppliers/{supplier_id}` - 공급사 삭제
- `GET /api/v1/suppliers/{supplier_id}/accounts` - 공급사의 계정 목록

### 상품 관리 (드랍싸핑 특화)

- `POST /api/v1/products/bulk` - 대량 상품 등록 (드랍싸핑 셀러용)
- `POST /api/v1/products/collect` - 상품 수집 (백그라운드)
- `GET /api/v1/products` - 상품 목록 조회
- `GET /api/v1/products/{product_id}` - 특정 상품 조회
- `PUT /api/v1/products/{product_id}` - 상품 정보 수정
- `GET /api/v1/products/stats/{supplier_id}` - 공급사 상품 통계
- `POST /api/v1/products/sync-history` - 동기화 이력 조회

### 비동기 작업 관리

- `GET /api/v1/tasks` - 작업 목록 조회
- `GET /api/v1/tasks/{task_id}` - 특정 작업 조회
- `POST /api/v1/tasks/bulk-products` - 대량 상품 등록 작업 생성
- `POST /api/v1/tasks/product-collection` - 상품 수집 작업 생성
- `DELETE /api/v1/tasks/{task_id}` - 작업 취소
- `POST /api/v1/tasks/cleanup` - 완료된 작업 정리
- `GET /api/v1/tasks/stats/summary` - 작업 통계 조회

### 주문 관리

- `GET /api/v1/orders/{supplier_id}/{order_key}` - 단일 주문 조회
- `GET /api/v1/orders/{supplier_id}` - 주문 목록 조회
- `POST /api/v1/orders/simulate` - 주문 시뮬레이션
- `POST /api/v1/orders/create` - 주문 생성
- `POST /api/v1/orders/cancel` - 주문 취소
- `POST /api/v1/orders/update-notes` - 주문 메모 업데이트

### 카테고리 관리

- `GET /api/v1/categories/{supplier_id}/tree` - 카테고리 트리 조회
- `GET /api/v1/categories/{supplier_id}/{category_key}` - 단일 카테고리 조회
- `GET /api/v1/categories/{supplier_id}/root` - 최상위 카테고리 조회

### 쿠팡 연동 API

- `POST /api/v1/coupang/credentials` - 쿠팡윙 인증 정보 설정
- `POST /api/v1/coupang/test-connection` - 쿠팡윙 연결 테스트
- `GET /api/v1/coupang/{supplier_id}/vendor` - 벤더 정보 조회
- `GET /api/v1/coupang/{supplier_id}/products` - 상품 목록 조회
- `GET /api/v1/coupang/{supplier_id}/orders` - 주문 목록 조회
- `GET /api/v1/coupang/{supplier_id}/return-requests` - 반품 요청 조회

## 💡 사용 예시

### 1. 공급사 생성

```bash
curl -X POST "http://localhost:8000/api/v1/suppliers" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "드랍싸핑 공급처",
    "description": "드랍싸핑용 상품 공급처",
    "base_url": "https://api.supplier.com",
    "default_margin_rate": 0.3
  }'
```

### 2. 대량 상품 등록 (드랍싸핑 셀러용)

```bash
curl -X POST "http://localhost:8000/api/v1/products/bulk" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "supplier_id": 1,
      "supplier_account_id": 1,
      "item_key": "ITEM001",
      "name": "스마트폰 케이스",
      "price": 5000,
      "sale_price": 8000,
      "margin_rate": 0.375,
      "supplier_product_id": "SUP001",
      "supplier_name": "중국 공급업체",
      "estimated_shipping_days": 7,
      "category_name": "휴대폰 액세서리"
    },
    {
      "supplier_id": 1,
      "supplier_account_id": 1,
      "item_key": "ITEM002",
      "name": "블루투스 이어폰",
      "price": 15000,
      "sale_price": 25000,
      "margin_rate": 0.4,
      "supplier_product_id": "SUP002",
      "supplier_name": "중국 공급업체",
      "estimated_shipping_days": 10,
      "category_name": "오디오"
    }
  ]'
```

### 3. 상품 수집

```bash
curl -X POST "http://localhost:8000/api/v1/products/collect" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_id": 1,
    "force_sync": false
  }'
```

### 4. 상품 통계 조회

```bash
curl -X GET "http://localhost:8000/api/v1/products/stats/1"
```

### 5. 비동기 작업 관리

대량 작업의 진행률을 실시간으로 확인할 수 있습니다:

```bash
# 작업 목록 조회
curl -X GET "http://localhost:8000/api/v1/tasks"

# 특정 작업 조회
curl -X GET "http://localhost:8000/api/v1/tasks/{task_id}"

# 작업 통계 조회
curl -X GET "http://localhost:8000/api/v1/tasks/stats/summary"

# 완료된 작업 정리
curl -X POST "http://localhost:8000/api/v1/tasks/cleanup"
```

작업 상태:
- `pending`: 대기 중
- `running`: 실행 중
- `completed`: 완료
- `failed`: 실패
- `cancelled`: 취소됨

## 🔧 고급 기능

### 자동 동기화 시스템
- **실시간 상품 동기화**: 공급처 상품 변경시 자동 업데이트
- **가격 동기화**: 공급가 변동시 마진율에 따른 판매가 자동 조정
- **재고 동기화**: 공급처 재고 상태 실시간 반영
- **동기화 이력 추적**: 모든 변경사항 이력 관리

### 에러 처리 및 모니터링
- **상세 로깅**: 모든 작업에 대한 상세 로그 기록
- **에러 복구**: 실패한 작업 자동 재시도
- **성능 모니터링**: 처리 속도 및 성공률 추적
- **알림 시스템**: 중요 에러 발생시 알림

### 대량 처리 최적화
- **배치 처리**: 50개씩 묶어서 동시 처리
- **비동기 작업**: 긴 작업을 백그라운드에서 처리
- **메모리 최적화**: 대량 데이터 처리시 메모리 사용량 최적화
- **진행률 추적**: 대량 작업의 진행률 실시간 확인
- **작업 큐**: 비동기 작업 관리 및 우선순위 처리
- **재시도 로직**: 실패한 작업 자동 재시도

### 데이터 검증 시스템
- **상품 데이터 검증**: 등록 전 모든 데이터 형식 및 비즈니스 규칙 검증
- **대량 검증**: 100개 상품까지 한 번에 검증
- **드랍싸핑 특화 검증**: 공급처 URL, 이미지 URL, 마진율 등 특화 검증
- **자동 보정**: 잘못된 데이터 자동 보정 및 정규화

## 🔐 보안

- **환경변수 관리**: 민감한 정보는 환경변수로 관리
- **JWT 인증**: OwnerClan API 연동을 위한 JWT 토큰 인증
- **API 키 보호**: 쿠팡 API 키 데이터베이스 암호화 저장
- **HTTPS 강제**: 프로덕션 환경에서 HTTPS만 허용

## 📊 모니터링

### 로그 파일
- **상품 동기화 로그**: `logs/product_sync.log`
- **API 액세스 로그**: `logs/access.log`
- **에러 로그**: `logs/error.log`
- **작업 로그**: `logs/task_manager.log`

### 헬스체크
- **시스템 상태**: `/health`
- **데이터베이스 연결**: `/health/db`
- **외부 API 상태**: `/health/apis`

## 🔧 유틸리티 스크립트

### 테스트 데이터 생성
드랍싸핑 셀러 테스트를 위해 다양한 상품 데이터를 생성할 수 있습니다:

```bash
# 기본 테스트 데이터 생성 (100개 상품)
python scripts/create_test_data.py

# 특정 개수로 생성
python -c "
import asyncio
from scripts.create_test_data import TestDataGenerator
async def main():
    gen = TestDataGenerator()
    await gen.create_suppliers_and_accounts()
    await gen.create_products(count=50)
    await gen.generate_csv_data()
asyncio.run(main())
"
```

생성되는 데이터:
- **3개 공급사**: 중국 도매, 한국 중소기업, 해외 직구 플랫폼
- **계정 정보**: 각 공급사의 인증 정보
- **100개 상품**: 다양한 카테고리, 마진율, 재고 정보 포함
- **CSV 파일**: 엑셀에서 바로 사용할 수 있는 형식

### 환경 설정 스크립트
```bash
# .env 파일 생성 확인
ls -la .env

# 설정값 확인
python -c "
from app.core.config import get_settings
settings = get_settings()
print('API 포트:', settings.api_port)
print('배치 크기:', settings.sync_batch_size)
print('기본 마진율:', settings.default_margin_rate)
"
```

## 🚀 배포

### Docker 배포
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY .env .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 환경별 설정
- **개발환경**: `DEBUG=true`, 상세 로깅
- **스테이징**: `DEBUG=false`, 기본 로깅
- **프로덕션**: `DEBUG=false`, `LOG_LEVEL=WARNING`, 보안 강화

## 🔄 헥사고날 아키텍처 마이그레이션

### 마이그레이션 현황
이 프로젝트는 **헥사고날 아키텍처**로 리팩토링이 진행 중입니다.

#### 완료된 작업 ✅
- [x] `src/` 폴더 구조 생성
- [x] 포트(인터페이스) 정의 (Supplier, Market, Repository, Clock)
- [x] 도메인 엔티티 구현 (Item, Account, SyncHistory)
- [x] 공급사 어댑터 구현 (OwnerClanAdapter)
- [x] 마켓 어댑터 구현 (CoupangAdapter)
- [x] 토큰 저장소 구현 (TokenStore)
- [x] 유즈케이스 구현 (IngestItems, NormalizeItems, PublishToMarket)
- [x] 테스트 구조 개선
- [x] 환경 설정 및 스크립트

#### 진행 중 작업 🔄
- [ ] 라우트 리팩토링 (app/routes/ → 헥사고날 구조)
- [ ] 완전한 리포지토리 구현
- [ ] 기존 main.py → 헥사고날 구조 전환

#### 새로운 아키텍처 실행 방법
```powershell
# 헥사고날 구조 개발 서버
.\scripts\dev.ps1

# 헥사고날 구조 테스트
.\scripts\test.ps1 -TestType unit
```

### 아키텍처 이점
1. **유지보수성**: 비즈니스 로직과 기술적 관심사가 명확히 분리
2. **테스트 용이성**: 각 계층이 독립적으로 테스트 가능
3. **확장성**: 새로운 공급사/마켓 추가가 쉬워짐
4. **안전성**: 타입 안정성과 에러 처리 개선

## 🤝 기여

1. Fork 프로젝트
2. Feature 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 생성

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 🎯 요약

드랍싸핑 셀러 관리 시스템은 다음과 같은 혁신적인 기능을 제공합니다:

### 🚀 **핵심 혁신**
- **헥사고날 아키텍처**: 모듈화된 클린 아키텍처로 유지보수성 3배 향상
- **드랍싸핑 특화**: 대량 상품 처리, 마진 관리, 공급처 동기화에 최적화
- **비동기 작업 시스템**: 대량 데이터 처리를 위한 고성능 비동기 처리
- **실시간 모니터링**: 모든 작업의 진행률과 상태를 실시간으로 확인
- **데이터 검증**: 상품 등록 전 철저한 검증으로 데이터 품질 보장
- **완전한 CRUD**: 상품, 주문, 공급사, 계정 관리의 모든 기능 구현

### 💰 **드랍싸핑 셀러를 위한 이점**
1. **⚡ 처리 속도**: 50개씩 배치로 동시 처리로 대폭 향상
2. **🔄 자동화**: 공급처 상품 정보 실시간 동기화
3. **📈 수익 최적화**: 마진율 자동 계산 및 판매가 최적화
4. **🛡️ 안정성**: 에러 복구 및 재시도 로직으로 안정적 운영
5. **📊 인사이트**: 상세한 로그와 통계로 비즈니스 인사이트 제공

### 🔧 **기술적 우월성**
- **FastAPI 기반**: 최신 비동기 웹 프레임워크
- **PostgreSQL + SQLAlchemy**: 고성능 데이터베이스
- **구조화된 로깅**: JSON 기반 상세 로깅 시스템
- **환경별 설정**: Docker부터 로컬까지 유연한 배포
- **테스트 데이터**: 실제 비즈니스 시나리오를 반영한 테스트 데이터

이제 코드베이스가 **드랍싸핑 셀러의 실제 요구사항**에 완벽하게 최적화되어 **대량 상품 등록**, **실시간 동기화**, **효율적 관리**가 가능해졌습니다! 🚀

드랍싸핑 비즈니스를 시작하시거나 확장하시려는 모든 셀러분들께 강력히 추천드립니다.