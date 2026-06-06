"""
routes/staged_files.py — GET /staged-files/<telegram_id>
Called by the VS Code extension sidebar to list pending staged files.
"""

from fastapi import APIRouter, HTTPException, Depends
from supabase_service import get_user_by_telegram_id, get_pending_files
from auth import require_api_key

router = APIRouter()


@router.get("/staged-files/{telegram_id}")
async def list_staged_files(telegram_id: str, _auth: str = Depends(require_api_key)):
    """Return all pending staged files for the extension sidebar."""
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not registered.")

    if user.get("status") == "banned":
        raise HTTPException(status_code=403, detail="Account suspended.")

    files = get_pending_files(telegram_id)

    return {
        "ok": True,
        "telegram_id": telegram_id,
        "repo": user.get("default_repo"),
        "branch": user.get("branch"),
        "count": len(files),
        "files": [
            {
                "id": f["id"],
                "filepath": f["filepath"],
                "file_size": f.get("file_size", 0),
                "is_binary": f.get("is_binary", False),
                "staged_at": f.get("staged_at", ""),
                "status": f.get("status", "pending"),
            }
            for f in files
        ],
    }
