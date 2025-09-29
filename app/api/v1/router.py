from fastapi import APIRouter
from app.api.v1.endpoints import suppliers, products, auth, orders, categories, coupang, tasks, ownerclan, websocket, progress, dashboard

# 메인 API 라우터
api_router = APIRouter()

# 각 기능별 라우터 등록
api_router.include_router(
    suppliers.router,
    prefix="/suppliers",
    tags=["suppliers"]
)

api_router.include_router(
    products.router,
    prefix="/products",
    tags=["products"]
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    orders.router,
    prefix="/orders",
    tags=["orders"]
)

api_router.include_router(
    categories.router,
    prefix="/categories",
    tags=["categories"]
)

api_router.include_router(
    coupang.router,
    prefix="/coupang",
    tags=["coupang"]
)

api_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["async-tasks"]
)

api_router.include_router(
    ownerclan.router,
    prefix="/ownerclan",
    tags=["ownerclan"]
)

api_router.include_router(
    websocket.router,
    prefix="/ws",
    tags=["websocket"]
)

api_router.include_router(
    progress.router,
    prefix="/progress",
    tags=["progress"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"]
)

