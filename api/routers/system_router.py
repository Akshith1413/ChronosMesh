"""Platform status for the Overview / Observability screens."""

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.services.execution_service import ExecutionService, get_service

router = APIRouter()


@router.get("/status", summary="Storage health, queue backlog, limits and observability links")
async def status(_: dict = Depends(get_current_user), svc: ExecutionService = Depends(get_service)):
    return svc.system_status()
