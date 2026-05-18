from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/clerk")
async def clerk_webhook(request: Request) -> dict[str, str]:
    # TODO: verify Svix signature, handle user.created / org.created → upsert tenant
    return {"received": "true"}


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    # TODO: verify Stripe signature, handle invoice / subscription / meter events
    return {"received": "true"}
