from fastapi import APIRouter, Depends
from typing import Optional
from app.models.clinic.dao import ClinicDAO
from app.models.clinic.schemas import SClinic
from app.models.clinic.rb import RBClinic

router = APIRouter(prefix="/clinics", tags=["Clinic"])


@router.get("/{id}", summary="Get clinic by ID")
async def find_one_or_none_by_id(request_body: RBClinic = Depends()) -> Optional[SClinic]:
    return await ClinicDAO.find_one_or_none_by_id(**request_body.to_dict())


@router.get("/", summary="Get all clinics")
async def find_all() -> list[SClinic]:
    return await ClinicDAO.find_all()


@router.post("/add/", summary="Add new clinic record")
async def add_clinic(clinic: SClinic) -> dict:
    clinic = await ClinicDAO.add(**clinic.dict())
    if clinic:
        return {"message": "Clinic entry successfully added!", "clinic": clinic}
    else:
        return {"message": "Error adding clinic entry!"}


@router.delete("/delete/{id}", summary="Delete clinic by ID")
async def delete(id: int) -> dict:
    check = await ClinicDAO.delete(id=id)
    if check:
        return {"message": f"Clinic with ID {id} deleted!"}
    else:
        return {"message": "Error deleting clinic!"}

