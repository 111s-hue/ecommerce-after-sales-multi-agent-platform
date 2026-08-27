from fastapi import APIRouter

from app.api.routers import (
    after_sales,
    auth,
    chat,
    knowledge,
    monitoring,
    notifications,
    operations,
    users,
)

router = APIRouter()
router.include_router(auth.router)
router.include_router(after_sales.router)
router.include_router(users.router)
router.include_router(notifications.router)
router.include_router(chat.router)
router.include_router(operations.router)
router.include_router(knowledge.router)
router.include_router(monitoring.router)
