from app.models.dao.base import BaseDao
from app.models.session.models import Session


class SessionDAO(BaseDao):
    model = Session
