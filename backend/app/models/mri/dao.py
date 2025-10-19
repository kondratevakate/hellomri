from app.models.dao.base import BaseDao
from app.models.mri.models import Mri


class MriDAO(BaseDao):
    model = Mri
