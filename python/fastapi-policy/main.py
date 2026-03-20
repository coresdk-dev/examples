"""
CoreSDK — FastAPI Rego policy enforcement.

Install:  pip install coresdk fastapi uvicorn
Run:      uvicorn main:app --reload
"""
from fastapi import FastAPI, Depends
from coresdk.fastapi import require_auth, require_policy, CurrentUser

app = FastAPI()


@app.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    user: CurrentUser = Depends(require_policy("documents.read", resource_id_param="doc_id")),
):
    return {"doc_id": doc_id, "content": "..."}


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user: CurrentUser = Depends(require_policy("documents.delete", resource_id_param="doc_id")),
):
    return {"deleted": doc_id}
