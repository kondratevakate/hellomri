from app.models.dao.base import BaseDao
from app.models.user.models import User


class UsersDAO(BaseDao):
    model = User
    

