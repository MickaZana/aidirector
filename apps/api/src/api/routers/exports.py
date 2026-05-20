from fastapi import APIRouter

from api.deps import Tenant_

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{export_id}/url")
def get_export_url(export_id: str, tenant_id: Tenant_) -> dict[str, str]:
    raise NotImplementedError("Presigned export URL not wired")
