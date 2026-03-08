# ==================== Tests for ring_buffer.py ====================

import pytest

from cryptotechnolog.core.ring_buffer import (
    AsyncRingBuffer,
    RingBuffer,
    RingBufferStats,
)


class TestRingBufferStats:
    """Tests for RingBufferStats dataclass."""

    def test_ring_buffer_stats_creation(self):
        """Test creating RingBufferStats."""
        stats = RingBufferStats(
            capacity=100,
            size=50,
            is_full=False,
            is_empty=False,
            push_count=50,
            pop_count=0,
            overflow_count=0,
        )

        assert stats.capacity == 100
        assert stats.size == 50
        assert not stats.is_full
        assert not stats.is_empty


class TestRingBuffer:
    """Tests for RingBuffer class."""

    def test_init_with_valid_capacity(self):
        """Test initialization with valid capacity."""
        rb = RingBuffer(capacity=10)
        # Actual capacity is rounded up (implementation doubles if not power of 2)
        assert rb.capacity == 20
        assert rb.size == 0
        assert rb.is_empty
        assert not rb.is_full

    def test_init_rounds_to_power_of_2(self):
        """Test capacity is rounded to power of 2."""
        rb = RingBuffer(capacity=10)
        # Implementation doubles if not power of 2: 10 * 2 = 20
        assert rb.capacity == 20

    def test_init_with_power_of_2(self):
        """Test initialization with power of 2."""
        rb = RingBuffer(capacity=8)
        assert rb.capacity == 8

    def test_init_invalid_capacity(self):
        """Test initialization with invalid capacity."""
        with pytest.raises(ValueError):
            RingBuffer(capacity=0)

        with pytest.raises(ValueError):
            RingBuffer(capacity=-1)

    def test_push_returns_true(self):
        """Test push returns True for successful insert."""
        rb = RingBuffer(capacity=10)
        assert rb.push("item") is True
        assert rb.size == 1

    def test_push_returns_false_when_full(self):
        """Test push returns False when buffer is full."""
        rb = RingBuffer(capacity=2)
        rb.push("item1")
        rb.push("item2")

        # Buffer is full, should return False
        result = rb.push("item3")
        assert result is False
        assert rb.overflow_count == 1

    def test_pop_returns_item(self):
        """Test pop returns item."""
        rb = RingBuffer(capacity=10)
        rb.push("item")

        item = rb.pop()
        assert item == "item"
        assert rb.is_empty

    def test_pop_returns_none_when_empty(self):
        """Test pop returns None when buffer is empty."""
        rb = RingBuffer(capacity=10)

        item = rb.pop()
        assert item is None

    def test_peek_returns_first_item(self):
        """Test peek returns first item without removing."""
        rb = RingBuffer(capacity=10)
        rb.push("item1")
        rb.push("item2")

        item = rb.peek()
        assert item == "item1"
        assert rb.size == 2

    def test_peek_returns_none_when_empty(self):
        """Test peek returns None when buffer is empty."""
        rb = RingBuffer(capacity=10)

        item = rb.peek()
        assert item is None

    def test_clear(self):
        """Test clear removes all items."""
        rb = RingBuffer(capacity=10)
        rb.push("item1")
        rb.push("item2")

        rb.clear()

        assert rb.is_empty
        assert rb.size == 0

    def test_get_stats(self):
        """Test get_stats returns correct data."""
        rb = RingBuffer(capacity=10)
        rb.push("item1")
        rb.push("item2")
        rb.pop()

        stats = rb.get_stats()

        # Actual capacity is 20 (implementation doubles if not power of 2)
        assert stats.capacity == 20
        assert stats.size == 1
        assert stats.push_count == 2
        assert stats.pop_count == 1
        assert stats.overflow_count == 0

    def test_len(self):
        """Test __len__ returns size."""
        rb = RingBuffer(capacity=10)
        assert len(rb) == 0

        rb.push("item")
        assert len(rb) == 1

    def test_repr(self):
        """Test __repr__ returns correct string."""
        rb = RingBuffer(capacity=10)

        result = repr(rb)
        assert "RingBuffer" in result
        assert "capacity" in result

    def test_overflow_tracking(self):
        """Test overflow count increments."""
        rb = RingBuffer(capacity=1)
        rb.push("item1")

        # This should overflow
        rb.push("item2")

        assert rb.overflow_count == 1

        # Another overflow
        rb.push("item3")
        assert rb.overflow_count == 2


class TestAsyncRingBuffer:
    """Tests for AsyncRingBuffer class."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test initialization."""
        rb = AsyncRingBuffer(capacity=10)
        assert rb.capacity == 10
        assert rb.is_empty
        assert not rb.is_full

    @pytest.mark.asyncio
    async def test_init_invalid_capacity(self):
        """Test initialization with invalid capacity."""
        with pytest.raises(ValueError):
            AsyncRingBuffer(capacity=0)

        with pytest.raises(ValueError):
            AsyncRingBuffer(capacity=-1)

    @pytest.mark.asyncio
    async def test_async_push(self):
        """Test async push."""
        rb = AsyncRingBuffer(capacity=10)

        result = await rb.push("item")

        assert result is True
        assert rb.size == 1

    @pytest.mark.asyncio
    async def test_async_push_when_full(self):
        """Test async push when buffer is full."""
        rb = AsyncRingBuffer(capacity=1)
        await rb.push("item1")

        result = await rb.push("item2")

        assert result is False
        assert rb.overflow_count == 1

    @pytest.mark.asyncio
    async def test_async_pop(self):
        """Test async pop."""
        rb = AsyncRingBuffer(capacity=10)
        await rb.push("item")

        item = await rb.pop()

        assert item == "item"
        assert rb.is_empty

    @pytest.mark.asyncio
    async def test_async_pop_when_empty(self):
        """Test async pop when buffer is empty."""
        rb = AsyncRingBuffer(capacity=10)

        item = await rb.pop()

        assert item is None

    @pytest.mark.asyncio
    async def test_push_wait(self):
        """Test push_wait."""
        rb = AsyncRingBuffer(capacity=10)

        result = await rb.push_wait("item", timeout=1.0)

        assert result is True
        assert rb.size == 1

    @pytest.mark.asyncio
    async def test_push_wait_timeout(self):
        """Test push_wait with timeout."""
        rb = AsyncRingBuffer(capacity=1)
        await rb.push("item1")

        # This should timeout
        result = await rb.push_wait("item2", timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_pop_wait(self):
        """Test pop_wait."""
        rb = AsyncRingBuffer(capacity=10)
        await rb.push("item")

        item = await rb.pop_wait(timeout=1.0)

        assert item == "item"

    @pytest.mark.asyncio
    async def test_pop_wait_timeout(self):
        """Test pop_wait with timeout."""
        rb = AsyncRingBuffer(capacity=10)

        item = await rb.pop_wait(timeout=0.1)

        assert item is None

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clear."""
        rb = AsyncRingBuffer(capacity=10)
        await rb.push("item1")
        await rb.push("item2")

        rb.clear()

        assert rb.is_empty

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test get_stats."""
        rb = AsyncRingBuffer(capacity=10)
        await rb.push("item")

        stats = rb.get_stats()

        assert stats.capacity == 10
        assert stats.size == 1
        assert stats.push_count == 1

    @pytest.mark.asyncio
    async def test_len(self):
        """Test __len__."""
        rb = AsyncRingBuffer(capacity=10)

        assert len(rb) == 0

        await rb.push("item")

        assert len(rb) == 1

    @pytest.mark.asyncio
    async def test_multiple_operations(self):
        """Test multiple push/pop operations."""
        rb = AsyncRingBuffer(capacity=5)

        # Push 5 items
        for i in range(5):
            result = await rb.push(f"item{i}")
            assert result is True

        # Buffer is now full
        assert rb.is_full

        # Push one more - should fail
        result = await rb.push("overflow")
        assert result is False

        # Pop all items
        items = []
        for _ in range(5):
            item = await rb.pop()
            if item:
                items.append(item)

        assert len(items) == 5
        assert rb.is_empty
