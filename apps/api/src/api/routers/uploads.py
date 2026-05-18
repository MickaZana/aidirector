from fastapi import APIRouter
from pydantic import BaseModel

from api.deps import Tenant

router = APIRouter(prefix="/uploads", tags=["uploads"])


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int


class PresignResponse(BaseModel):
    upload_id: str
    url: str
    fields: dict[str, str]
    r2_key: str


@router.post("/presign", response_model=PresignResponse)
def presign(req: PresignRequest, tenant_id: Tenant) -> PresignResponse:
    # TODO: implement R2 presign via api.services.r2.presign_post
    # Stub returns shape so the dashboard can integrate against the contract.
    raise NotImplementedError("R2 presign not wired yet — see plan §15 phase 0 gate 4")
