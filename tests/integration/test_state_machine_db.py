# ==================== CRYPTOTEHNOLOG State Machine DB Integration Tests ====================
# Integration tests for State Machine with PostgreSQL audit trail

import pytest
from asyncpg import connect as asyncpg_connect

from src.core.state_machine import StateMachine
from src.core.state_machine_enums import SystemState


@pytest.mark.integration
class TestStateMachinePostgreSQL:
    """Test cases for State Machine PostgreSQL integration."""

    @pytest.fixture
    async def sm_with_db(self, test_settings):
        """Create State Machine with PostgreSQL connection."""
        # Создаём подключение к PostgreSQL (ТЕСТОВОЙ БД)
        db = await asyncpg_connect(test_settings.postgres_test_async_url)
        
        # Очищаем состояние перед тестом
        await db.execute("DELETE FROM state_transitions")
        await db.execute("UPDATE state_machine_states SET current_state = 'boot', version = 0 WHERE id = 1")
        await db.execute("COMMIT")
        
        # Создаём State Machine с подключением к БД
        sm = StateMachine(db_manager=db)
        await sm.initialize()
        
        yield sm
        
        # Очистка: удаляем тестовые записи
        await db.execute("DELETE FROM state_transitions")
        await db.execute("UPDATE state_machine_states SET current_state = 'boot', version = 0 WHERE id = 1")
        await db.execute("COMMIT")
        await db.close()

    @pytest.mark.asyncio
    async def test_transition_saves_to_postgres(self, sm_with_db):
        """Test that transition is saved to PostgreSQL."""
        sm = sm_with_db
        
        # Выполняем переход
        result = await sm.transition(
            SystemState.INIT,
            trigger="SYSTEM_STARTUP",
            operator="test_operator",
            metadata={"test": True}
        )
        
        assert result.success is True
        assert sm.current_state == SystemState.INIT
        assert sm.version == 1
        
        # Проверяем, что переход записан в БД
        row = await sm._db.fetchrow(
            "SELECT * FROM state_transitions WHERE operator = $1 ORDER BY id DESC LIMIT 1",
            "test_operator"
        )
        
        assert row is not None
        assert row["from_state"] == "boot"
        assert row["to_state"] == "init"
        assert row["trigger"] == "SYSTEM_STARTUP"
        assert row["operator"] == "test_operator"

    @pytest.mark.asyncio
    async def test_multiple_transitions_saved(self, sm_with_db):
        """Test that multiple transitions are saved to PostgreSQL."""
        sm = sm_with_db
        
        # Выполняем несколько переходов
        await sm.transition(SystemState.INIT, "SYSTEM_STARTUP", operator="test_operator")
        await sm.transition(SystemState.READY, "STRATEGIES_LOADED", operator="test_operator")
        await sm.transition(SystemState.TRADING, "ALL_CHECKS_PASSED", operator="test_operator")
        
        # Проверяем, что все переходы записаны в БД
        rows = await sm._db.fetch(
            "SELECT * FROM state_transitions WHERE operator = 'test_operator' ORDER BY id"
        )
        
        assert len(rows) == 3
        assert rows[0]["to_state"] == "init"
        assert rows[1]["to_state"] == "ready"
        assert rows[2]["to_state"] == "trading"

    @pytest.mark.asyncio
    async def test_state_machine_states_table(self, sm_with_db):
        """Test that state_machine_states table is updated."""
        sm = sm_with_db
        
        # Выполняем переход
        await sm.transition(SystemState.INIT, "SYSTEM_STARTUP", operator="test_operator")
        
        # Проверяем, что состояние обновлено в БД
        row = await sm._db.fetchrow(
            "SELECT * FROM state_machine_states WHERE id = 1"
        )
        
        assert row is not None
        assert row["current_state"] == "init"
        assert row["version"] >= 1

    @pytest.mark.asyncio
    async def test_audit_trail_metadata(self, sm_with_db):
        """Test that metadata is saved in audit trail."""
        import json
        
        sm = sm_with_db
        
        metadata = {
            "strategy_count": 5,
            "risk_limits_loaded": True,
            "execution_layer_ready": True
        }
        
        # Выполняем переход с метаданными (boot -> init -> ready)
        await sm.transition(
            SystemState.INIT,
            "SYSTEM_STARTUP",
            operator="test_operator",
            metadata={"init": True}
        )
        
        await sm.transition(
            SystemState.READY,
            "STRATEGIES_LOADED",
            operator="test_operator",
            metadata=metadata
        )
        
        # Проверяем метаданные в БД
        row = await sm._db.fetchrow(
            "SELECT metadata FROM state_transitions WHERE operator = 'test_operator' ORDER BY id DESC LIMIT 1"
        )
        
        assert row is not None
        # metadata хранится как JSON строка
        saved_metadata = json.loads(row["metadata"])
        assert saved_metadata["strategy_count"] == 5
        assert saved_metadata["risk_limits_loaded"] is True


@pytest.mark.integration
class TestStateMachineAuditTrail:
    """Test cases for State Machine audit trail functionality."""

    @pytest.fixture
    async def clean_db(self, test_settings):
        """Provide clean database connection to test DB."""
        db = await asyncpg_connect(test_settings.postgres_test_async_url)
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_audit_events_table_exists(self, clean_db):
        """Test that audit_events table exists and has correct structure."""
        # Проверяем наличие таблицы
        table_exists = await clean_db.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'audit_events')"
        )
        assert table_exists is True
        
        # Проверяем структуру таблицы
        columns = await clean_db.fetch(
            """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'audit_events'
            ORDER BY ordinal_position
            """
        )
        
        column_names = [c["column_name"] for c in columns]
        assert "id" in column_names
        assert "event_type" in column_names
        assert "entity_type" in column_names
        assert "entity_id" in column_names
        assert "old_state" in column_names
        assert "new_state" in column_names
        assert "operator" in column_names
        assert "timestamp" in column_names

    @pytest.mark.asyncio
    async def test_state_transitions_table_structure(self, clean_db):
        """Test that state_transitions table has correct structure."""
        # Проверяем структуру таблицы
        columns = await clean_db.fetch(
            """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'state_transitions'
            ORDER BY ordinal_position
            """
        )
        
        column_names = [c["column_name"] for c in columns]
        assert "id" in column_names
        assert "from_state" in column_names
        assert "to_state" in column_names
        assert "trigger" in column_names
        assert "metadata" in column_names
        assert "operator" in column_names
        assert "timestamp" in column_names
        assert "duration_ms" in column_names

    @pytest.mark.asyncio
    async def test_state_machine_states_table_structure(self, clean_db):
        """Test that state_machine_states table has correct structure."""
        # Проверяем структуру таблицы
        columns = await clean_db.fetch(
            """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'state_machine_states'
            ORDER BY ordinal_position
            """
        )
        
        column_names = [c["column_name"] for c in columns]
        assert "id" in column_names
        assert "current_state" in column_names
        assert "version" in column_names
        assert "updated_at" in column_names


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
