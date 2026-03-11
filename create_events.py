import asyncio
import asyncpg


async def main():
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='bot_user',
        password='bot_password_dev',
        database='trading_test'
    )
    
    # Создаём таблицу events
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(100) NOT NULL,
            data JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            correlation_id UUID
        )
    ''')
    print('DONE: events table created')
    
    # Проверим
    result = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'events'"
    )
    print(f'Events table: {result}')
    
    await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
