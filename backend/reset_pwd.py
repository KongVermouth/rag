import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, update
from app.models.user import User
from app.core.security import get_password_hash

async def main():
    async with AsyncSessionLocal() as s:
        new_hash = get_password_hash("Admin@123")
        await s.execute(
            update(User)
            .where(User.username == "rag_admin")
            .values(password_hash=new_hash)
        )
        await s.commit()
        print("Password reset for rag_admin to Admin@123")

if __name__ == "__main__":
    asyncio.run(main())
