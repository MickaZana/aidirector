from fastapi import APIRouter

from api.deps import Tenant

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/portal")
def portal(tenant_id: Tenant) -> dict[str, str]:
    raise NotImplementedError("Stripe billing portal session not wired")


@router.get("/usage")
def usage(tenant_id: Tenant) -> dict[str, int]:
    return {"asr_minutes": 0, "gpu_seconds": 0, "exports": 0}
