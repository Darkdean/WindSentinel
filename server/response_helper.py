from typing import Any, Dict, Optional

def api_response(code: int, status: str, detail: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"code": code, "status": status, "detail": detail, "data": data or {}}

def api_success(data: Optional[Dict[str, Any]] = None, detail: Optional[str] = None) -> Dict[str, Any]:
    return api_response(200, "success", detail, data)

def api_error(code: int, detail: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return api_response(code, "error", detail, data)
