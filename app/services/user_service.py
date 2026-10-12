"""UserService managing user account lifecycles and validation."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.common import PaginationParams
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Business operations for user accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def create_user(self, payload: UserCreate) -> User:
        """Create a new user with duplicate email detection and bcrypt hashing."""
        email = payload.email.lower().strip()
        if await self.repo.email_exists(email):
            raise ConflictError(
                message=f"User with email '{email}' already exists",
                details={"email": email},
            )

        hashed_password = get_password_hash(payload.password)
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=payload.full_name.strip(),
            role=payload.role,
            is_active=True,
            is_verified=False,
        )
        return await self.repo.create(user)

    async def get_user_by_id(self, user_id: int) -> User:
        """Fetch user by ID or raise NotFoundError."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message=f"User with ID {user_id} not found", details={"user_id": user_id})
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Fetch user by email."""
        return await self.repo.get_by_email(email)

    async def list_users(self, params: PaginationParams) -> tuple[Sequence[User], int]:
        """Fetch paginated list of users."""
        items = await self.repo.list(offset=params.offset, limit=params.per_page)
        total = await self.repo.count()
        return items, total

    async def update_user(self, user_id: int, payload: UserUpdate) -> User:
        """Update existing user properties."""
        user = await self.get_user_by_id(user_id)

        update_data = payload.model_dump(exclude_unset=True)
        if "email" in update_data and update_data["email"]:
            new_email = update_data["email"].lower().strip()
            if await self.repo.email_exists(new_email, exclude_user_id=user_id):
                raise ConflictError(
                    message=f"Email '{new_email}' is already in use by another account",
                    details={"email": new_email},
                )
            update_data["email"] = new_email

        return await self.repo.update(user, update_data)

    async def delete_user(self, user_id: int) -> None:
        """Soft delete a user account."""
        user = await self.get_user_by_id(user_id)
        await self.repo.delete(user, soft=True)
