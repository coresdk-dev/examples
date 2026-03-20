"""
CoreSDK — FastAPI JWT auth in 10 lines.

Install:  pip install coresdk fastapi uvicorn
Run:      uvicorn main:app --reload
Try:      curl -H "Authorization: Bearer <token>" http://localhost:8000/me
"""
from fastapi import FastAPI, Depends
from coresdk.fastapi import require_auth, CurrentUser

app = FastAPI()


@app.get("/me")
async def me(user: CurrentUser = Depends(require_auth)):
    return {"user_id": user.sub, "tenant": user.tenant_id, "roles": user.roles}


@app.get("/admin")
async def admin(user: CurrentUser = Depends(require_auth("admin"))):
    return {"message": f"Hello admin {user.sub}"}
