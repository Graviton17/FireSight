from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, bool]:
    """Return a lightweight process liveness response."""
    return {"ok": True}
