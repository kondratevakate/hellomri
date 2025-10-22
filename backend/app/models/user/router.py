from fastapi import APIRouter, Depends
from app.models.user.dao import UsersDAO
from app.models.user.schemas import SUser
from typing import Optional
from app.models.user.rb import RBUser

router = APIRouter(prefix='/users', tags=['User'])

@router.get("/{id}", summary="Get user by ID")
async def find_one_or_none_by_id(request_body: RBUser = Depends()) -> Optional[SUser]:
    return await UsersDAO.find_one_or_none_by_id(**request_body.to_dict())


@router.get("/", summary="Get all users")
async def find_all() -> list[SUser]:
    return await UsersDAO.find_all()


@router.post("/add/")
async def add_user(user: SUser) -> dict:
    user = await UsersDAO.add(**user.dict())
    if user:
        return {"message": "User successfully added!", "user": user}
    else:
        return {"message": "Error adding user!"}


@router.delete("/delete/{id}")
async def delete(id: int) -> dict:
    check = await UsersDAO.delete(id=id)
    if check:
        return {"message": f"User with ID {id} deleted!"}
    else:
        return {"message": "Error deleting user!"}
