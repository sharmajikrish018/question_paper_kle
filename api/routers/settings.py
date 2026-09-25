"""api/routers/settings.py — Settings & LLM health check."""
from fastapi import APIRouter
from repositories.settings_repo import SettingsRepository

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings_api():
    repo = SettingsRepository()
    return {
        "course_info": repo.get("course_info", {}),
        "paper_rules": repo.get("paper_rules", {}),
        "privacy": repo.get("privacy_settings", {}),
    }


@router.patch("")
def update_settings(body: dict):
    repo = SettingsRepository()
    for key, value in body.items():
        repo.set(key, value)
    return {"ok": True}


@router.get("/health")
def health_check():
    try:
        from services.llm_provider import get_llm_provider
        llm = get_llm_provider()
        result = llm.health_check()
        return {"status": "ok", "message": result.message, "model": result.model}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
