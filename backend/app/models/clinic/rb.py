class RBClinic:
    def __init__(
        self,
        id: int | None = None,
        user_id: int | None = None,
        mri_id: int | None = None,
        submitted_at: str | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.mri_id = mri_id
        self.submitted_at = submitted_at

    def to_dict(self) -> dict:
        return {
            key: value
            for key, value in {
                "id": self.id,
                "user_id": self.user_id,
                "mri_id": self.mri_id,
                "submitted_at": self.submitted_at,
            }.items()
            if value is not None
        }

