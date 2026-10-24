from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.auth.schemas import StrictModel
from app.core.audit import audit, public_document, transaction
from app.core.database import get_db
from app.core.rbac import get_current_user, require_verified_owner_permission
from app.core.security import utcnow

router = APIRouter(prefix="/owner", tags=["owner"])


class Room(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    price: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")
    max_guests: int = Field(default=2, ge=1, le=100)


class Post(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)


def owned_query(resource_id, actor):
    if not ObjectId.is_valid(resource_id):
        raise HTTPException(404, "Resource not found")
    return {"_id": ObjectId(resource_id), "owner_id": actor["sub"]}


async def owned_resource(collection, resource_id, actor):
    query = owned_query(resource_id, actor)
    row = await get_db()[collection].find_one(query)
    if not row:
        raise HTTPException(404, "Resource not found")
    return row


async def insert_owned(collection, payload, actor, extra=None):
    doc = (
        payload.model_dump()
        | {"owner_id": actor["sub"], "created_at": utcnow()}
        | (extra or {})
    )
    async with transaction() as session:
        result = await get_db()[collection].insert_one(doc, session=session)
        await audit("create", collection, result.inserted_id, actor, session=session)
    return public_document(doc)


async def update_owned(collection, resource_id, payload, actor, extra=None):
    changes = payload.model_dump() | {"updated_at": utcnow()} | (extra or {})
    async with transaction() as session:
        row = await get_db()[collection].find_one(
            owned_query(resource_id, actor), session=session
        )
        if not row:
            raise HTTPException(404, "Resource not found")
        await get_db()[collection].update_one(
            owned_query(resource_id, actor), {"$set": changes}, session=session
        )
        await audit(
            "update",
            collection,
            resource_id,
            actor,
            session=session,
            details={"fields": sorted(payload.model_fields_set)},
        )
    return public_document(row | changes)


async def delete_owned(collection, resource_id, actor):
    async with transaction() as session:
        result = await get_db()[collection].delete_one(
            owned_query(resource_id, actor), session=session
        )
        if not result.deleted_count:
            raise HTTPException(404, "Resource not found")
        await audit("delete", collection, resource_id, actor, session=session)


@router.get("/ping")
async def ping_owner():
    return {"lane": "owner", "status": "ok"}


@router.get("/profile")
async def profile(actor=Depends(get_current_user)):
    if actor["realm"] != "admin_users" or actor["role"] != "poi_owner":
        raise HTTPException(403, "Owner account required")
    registration = await get_db()["poi_owner_registrations"].find_one(
        {"user_id": actor["sub"]}
    )
    return {
        "id": actor["sub"],
        "full_name": actor["full_name"],
        "is_verified": actor["is_verified"],
        "is_poi_owner_verified": actor["is_poi_owner_verified"],
        "registration": public_document(registration) if registration else None,
    }


@router.get("/rooms")
async def rooms(
    limit: int = Query(50, ge=1, le=100),
    actor=Depends(require_verified_owner_permission("menu.read")),
):
    return [
        public_document(row)
        async for row in get_db()["owner_rooms"]
        .find({"owner_id": actor["sub"]})
        .sort("_id", -1)
        .limit(limit)
    ]


@router.post("/rooms", status_code=201)
async def create_room(
    payload: Room, actor=Depends(require_verified_owner_permission("menu.create"))
):
    return await insert_owned("owner_rooms", payload, actor)


@router.get("/rooms/{room_id}")
async def room(
    room_id: str, actor=Depends(require_verified_owner_permission("menu.read"))
):
    return public_document(await owned_resource("owner_rooms", room_id, actor))


@router.patch("/rooms/{room_id}")
async def update_room(
    room_id: str,
    payload: Room,
    actor=Depends(require_verified_owner_permission("menu.update")),
):
    return await update_owned("owner_rooms", room_id, payload, actor)


@router.delete("/rooms/{room_id}", status_code=204)
async def delete_room(
    room_id: str, actor=Depends(require_verified_owner_permission("menu.delete"))
):
    await delete_owned("owner_rooms", room_id, actor)


@router.get("/posts")
async def posts(
    limit: int = Query(50, ge=1, le=100),
    actor=Depends(require_verified_owner_permission("content.read")),
):
    return [
        public_document(row)
        async for row in get_db()["owner_posts"]
        .find({"owner_id": actor["sub"]})
        .sort("_id", -1)
        .limit(limit)
    ]


@router.post("/posts", status_code=201)
async def create_post(
    payload: Post, actor=Depends(require_verified_owner_permission("content.create"))
):
    return await insert_owned("owner_posts", payload, actor, {"status": "draft"})


@router.get("/posts/{post_id}")
async def post(
    post_id: str, actor=Depends(require_verified_owner_permission("content.read"))
):
    return public_document(await owned_resource("owner_posts", post_id, actor))


@router.patch("/posts/{post_id}")
async def update_post(
    post_id: str,
    payload: Post,
    actor=Depends(require_verified_owner_permission("content.update")),
):
    return await update_owned(
        "owner_posts", post_id, payload, actor, {"status": "draft"}
    )


@router.post("/posts/{post_id}/submit")
async def submit_post(
    post_id: str, actor=Depends(require_verified_owner_permission("content.submit"))
):
    async with transaction() as session:
        query = owned_query(post_id, actor) | {"status": "draft"}
        result = await get_db()["owner_posts"].update_one(
            query,
            {"$set": {"status": "pending", "submitted_at": utcnow()}},
            session=session,
        )
        if not result.modified_count:
            await owned_resource("owner_posts", post_id, actor)
            raise HTTPException(409, "Only draft posts can be submitted")
        await audit("submit", "owner_posts", post_id, actor, session=session)
    return {"id": post_id, "status": "pending"}


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str, actor=Depends(require_verified_owner_permission("content.delete"))
):
    await delete_owned("owner_posts", post_id, actor)
