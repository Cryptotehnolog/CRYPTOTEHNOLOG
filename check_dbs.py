import asyncio
import asyncpg


async def main():
    try:
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            user='bot_user',
            password='bot_password_dev',
            database='postgres',
            timeout=5
        )
        result = await conn.fetch('SELECT datname FROM pg_database WHERE datistemplate = false')
        dbs = [r['datname'] for r in result]
        print('Available databases:', dbs)
        
        # Check tables in each
        for db in dbs:
            try:
                conn2 = await asyncpg.connect(
                    host='localhost', port=5432,
                    user='bot_user', password='bot_password_dev',
                    database=db, timeout=2
                )
                tables = await conn2.fetch(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
                table_names = [t['table_name'] for t in tables]
                print(f'{db}: {table_names}')
                await conn2.close()
            except Exception as e:
                print(f'{db}: error - {e}')
        
        await conn.close()
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    asyncio.run(main())
