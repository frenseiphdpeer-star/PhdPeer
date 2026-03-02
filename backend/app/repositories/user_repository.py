"""User repository."""
from uuid import UUID

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """Data access for User entities."""

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_active_by_id(self, user_id: UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_oauth(self, provider: str, provider_id: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.oauth_provider == provider, User.oauth_provider_id == provider_id)
            .first()
        )

    def create_user(self, **kwargs) -> User:
        user = User(**kwargs)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
