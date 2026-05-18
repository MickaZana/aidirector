from fastapi import APIRouter

from api.deps import Tenant

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{export_id}/url")
def get_export_url(export_id: str, tenant_id: Tenant) -> dict[str, str]:
    raise NotImplementedError("Presigned export URL not wired")
