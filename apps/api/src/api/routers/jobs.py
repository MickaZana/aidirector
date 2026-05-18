from fastapi import APIRouter
from pydantic import BaseModel

from api.deps import Tenant

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    upload_id: str
    intent: str = "auto_shorts"


class JobView(BaseModel):
    id: str
    upload_id: str
    status: str
    intent: str
    cost_cents: int = 0


@router.get("", response_model=list[JobView])
def list_jobs(tenant_id: Tenant) -> list[JobView]:
    return []


@router.post("", response_model=JobView)
def create_job(req: JobCreate, tenant_id: Tenant) -> JobView:
    raise NotImplementedError("Job creation not wired — needs Postgres + RQ")


@router.get("/{job_id}", response_model=JobView)
def get_job(job_id: str, tenant_id: Tenant) -> JobView:
    raise NotImplementedError
