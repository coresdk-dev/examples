"""
CoreSDK — FastAPI Rego policy enforcement.

Install:  pip install coresdk fastapi uvicorn
Run:      uvicorn main:app --reload
"""

from fastapi import FastAPI, Depends, HTTPException
from coresdk import SDK, Claims
from coresdk.middleware.fastapi import require_auth

sdk = SDK.from_env()
app = FastAPI()


@app.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    claims: Claims = Depends(require_auth(sdk)),
):
    allowed = sdk.evaluate_policy(
        "data.documents.allow",
        {
            "action": "read",
            "resource_id": doc_id,
            "roles": claims.roles,
        },
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Policy denied: documents.read")
    return {"doc_id": doc_id, "content": "..."}


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    claims: Claims = Depends(require_auth(sdk)),
):
    allowed = sdk.evaluate_policy(
        "data.documents.allow",
        {
            "action": "delete",
            "resource_id": doc_id,
            "roles": claims.roles,
        },
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Policy denied: documents.delete")
    return {"deleted": doc_id}
