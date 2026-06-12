import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

LARAVEL_DB_URL = os.getenv("LARAVEL_DB_URI", "mysql+aiomysql://root:@localhost:3306/rdadmin_realdealride")

engine = create_async_engine(LARAVEL_DB_URL)

async def test():
    try:
        async with engine.begin() as conn:
            res = await conn.execute(text('SHOW TABLES'))
            tables = res.all()
            print(f"Connection successful! Found {len(tables)} tables.")
            
            # Check if 'cars' table exists and query it
            res = await conn.execute(text("SELECT COUNT(*) FROM cars"))
            print(f"Total cars in database: {res.scalar()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
