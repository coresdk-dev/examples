"""
CoreSDK — FastAPI JWT auth in 10 lines.

Install:  pip install coresdk fastapi uvicorn
Run:      uvicorn main:app --reload
Try:      curl -H "Authorization: Bearer <token>" http://localhost:8000/me
"""

from fastapi import FastAPI, Depends
from coresdk import SDK, Claims
from coresdk.middleware.fastapi import require_auth

sdk = SDK.from_env()
app = FastAPI()


@app.get("/me")
async def me(claims: Claims = Depends(require_auth(sdk))):
    return {"user_id": claims.sub, "tenant": claims.tenant_id, "roles": claims.roles}


@app.get("/admin")
async def admin(claims: Claims = Depends(require_auth(sdk))):
    if "admin" not in claims.roles:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required")
    return {"message": f"Hello admin {claims.sub}"}
