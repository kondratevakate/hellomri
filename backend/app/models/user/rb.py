class RBUser:
    def __init__(
        self,
        id: int | None = None,
        email: str | None = None,
        hashed_password: str | None = None,  
    ):
        self.id = id
        self.email = email
        self.hashed_password = hashed_password

    def to_dict(self) -> dict:
        return {
            key: value for key, value in {
                "id": self.id,
                "email": self.email,
                "hashed_password": self.hashed_password,
            }.items() if value is not None
        }