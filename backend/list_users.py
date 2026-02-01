import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User

async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(select(User))
        users = r.scalars().all()
        for u in users:
            print(f"User: {u.username}, Role: {u.role}, ID: {u.id}")

if __name__ == "__main__":
    asyncio.run(main())
