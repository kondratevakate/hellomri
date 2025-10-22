from app.models.dao.base import BaseDao
from app.models.clinic.models import Clinic


class ClinicDAO(BaseDao):
    model = Clinic

