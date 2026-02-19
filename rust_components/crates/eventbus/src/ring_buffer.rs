// ==================== CRYPTOTEHNOLOG Lock-Free Ring Buffer ====================
// Lock-free ring buffer implementation using crossbeam and arrayvec
//
// This implementation provides:
// - Lock-free operations for high concurrency
// - Bounded capacity to prevent unbounded memory growth
// - Wait-free read operations
// - Lock-free write operations (may fail if full)
//
// Use cases:
// - Event bus with high throughput
// - Inter-component communication
// - Message passing between threads

use crossbeam::queue::SegQueue;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Lock-free ring buffer with bounded capacity
///
/// This ring buffer provides lock-free operations for concurrent access.
/// It's designed for high-throughput scenarios where contention is expected.
///
/// # Type Parameters
///
/// * `T` - The type of items stored in the ring buffer
/// * `N` - The capacity of the ring buffer (must be a power of 2)
///
/// # Example
///
/// ```rust
/// use cryptotechnolog_eventbus::LockFreeRingBuffer;
///
/// let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();
///
/// // Write (lock-free, may fail if full)
/// buffer.push(42).unwrap();
///
/// // Read (wait-free, returns None if empty)
/// let item = buffer.pop();
/// ```
pub struct LockFreeRingBuffer<T, const N: usize> {
    /// Ring buffer storage (vector of SegQueue for heap allocation)
    buffer: Vec<SegQueue<T>>,
    /// Current write index (atomic for lock-free updates)
    write_index: AtomicUsize,
    /// Current read index (atomic for lock-free updates)
    read_index: AtomicUsize,
}

impl<T, const N: usize> LockFreeRingBuffer<T, N> {
    /// Create a new lock-free ring buffer
    ///
    /// # Panics
    ///
    /// Panics if N is not a power of 2
    #[inline]
    pub fn new() -> Self {
        assert!(
            N.is_power_of_two(),
            "Ring buffer capacity must be a power of 2"
        );

        // Create N SegQueue instances in a Vec (heap allocated)
        let buffer: Vec<SegQueue<T>> = (0..N).map(|_| SegQueue::new()).collect();

        Self {
            buffer,
            write_index: AtomicUsize::new(0),
            read_index: AtomicUsize::new(0),
        }
    }

    /// Push an item into the ring buffer (lock-free)
    ///
    /// This operation is lock-free but may fail if the buffer is full.
    /// Returns `Ok(())` on success, `Err(item)` if the buffer is full.
    ///
    /// # Arguments
    ///
    /// * `item` - The item to push
    ///
    /// # Returns
    ///
    /// * `Ok(())` - Item was successfully pushed
    /// * `Err(item)` - Buffer is full, item returned back
    #[inline]
    pub fn push(&self, item: T) -> Result<(), T> {
        // Get current indices
        let write_idx = self.write_index.load(Ordering::Relaxed);
        let read_idx = self.read_index.load(Ordering::Acquire);

        // Check if buffer is full
        if write_idx - read_idx >= N {
            return Err(item);
        }

        // Calculate slot index using modulo (fast for power of 2)
        let slot = write_idx & (N - 1);

        // Push to the selected queue
        self.buffer[slot].push(item);

        // Increment write index
        self.write_index.store(write_idx + 1, Ordering::Release);

        Ok(())
    }

    /// Pop an item from the ring buffer (wait-free)
    ///
    /// This operation is wait-free and will return immediately.
    /// Returns `Some(item)` if an item is available, `None` if empty.
    ///
    /// # Returns
    ///
    /// * `Some(item)` - Item was successfully popped
    /// * `None` - Buffer is empty
    #[inline]
    pub fn pop(&self) -> Option<T> {
        // Get current indices
        let read_idx = self.read_index.load(Ordering::Relaxed);
        let write_idx = self.write_index.load(Ordering::Acquire);

        // Check if buffer is empty
        if read_idx >= write_idx {
            return None;
        }

        // Calculate slot index using modulo (fast for power of 2)
        let slot = read_idx & (N - 1);

        // Try to pop from the selected queue
        let item = self.buffer[slot].pop()?;

        // Increment read index only if we successfully popped
        self.read_index.store(read_idx + 1, Ordering::Release);

        Some(item)
    }

    /// Get the current number of items in the buffer
    ///
    /// This is an estimate and may not be perfectly accurate
    /// due to concurrent modifications.
    #[inline]
    pub fn len(&self) -> usize {
        let write_idx = self.write_index.load(Ordering::Relaxed);
        let read_idx = self.read_index.load(Ordering::Relaxed);
        write_idx.saturating_sub(read_idx)
    }

    /// Check if the buffer is empty
    #[inline]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Check if the buffer is full
    #[inline]
    pub fn is_full(&self) -> bool {
        self.len() >= N
    }

    /// Get the capacity of the buffer
    #[inline]
    pub const fn capacity(&self) -> usize {
        N
    }

    /// Clear all items from the buffer
    ///
    /// Note: This is not atomic and should only be called when
    /// no other threads are accessing the buffer.
    #[inline]
    pub fn clear(&self) {
        while self.pop().is_some() {}
    }
}

impl<T, const N: usize> Default for LockFreeRingBuffer<T, N> {
    #[inline]
    fn default() -> Self {
        Self::new()
    }
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ring_buffer_new() {
        let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();
        assert_eq!(buffer.capacity(), 1024);
        assert!(buffer.is_empty());
        assert!(!buffer.is_full());
    }

    #[test]
    fn test_ring_buffer_push_pop() {
        let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();

        assert!(buffer.push(42).is_ok());
        assert_eq!(buffer.pop(), Some(42));
        assert!(buffer.is_empty());
    }

    #[test]
    fn test_ring_buffer_ordering() {
        let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();

        for i in 0..10 {
            assert!(buffer.push(i).is_ok());
        }

        for i in 0..10 {
            assert_eq!(buffer.pop(), Some(i));
        }
    }

    #[test]
    fn test_ring_buffer_full() {
        let buffer: LockFreeRingBuffer<i32, 16> = LockFreeRingBuffer::new();

        // Fill buffer
        for i in 0..16 {
            assert!(buffer.push(i).is_ok());
        }

        assert!(buffer.is_full());

        // Should fail to push when full
        assert!(buffer.push(999).is_err());
    }

    #[test]
    fn test_ring_buffer_empty() {
        let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();

        assert!(buffer.is_empty());
        assert_eq!(buffer.pop(), None);
    }

    #[test]
    fn test_ring_buffer_len() {
        let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();

        assert_eq!(buffer.len(), 0);

        for i in 0..10 {
            buffer.push(i).unwrap();
        }

        assert_eq!(buffer.len(), 10);

        for _ in 0..5 {
            buffer.pop();
        }

        assert_eq!(buffer.len(), 5);
    }

    #[test]
    fn test_ring_buffer_clear() {
        let buffer: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();

        for i in 0..10 {
            buffer.push(i).unwrap();
        }

        buffer.clear();
        assert!(buffer.is_empty());
        assert_eq!(buffer.len(), 0);
    }

    #[test]
    fn test_ring_buffer_power_of_two() {
        // Should compile fine
        let _buffer1: LockFreeRingBuffer<i32, 16> = LockFreeRingBuffer::new();
        let _buffer2: LockFreeRingBuffer<i32, 32> = LockFreeRingBuffer::new();
        let _buffer3: LockFreeRingBuffer<i32, 1024> = LockFreeRingBuffer::new();
    }

    #[test]
    #[should_panic]
    fn test_ring_buffer_not_power_of_two() {
        // Should panic at runtime
        let _buffer: LockFreeRingBuffer<i32, 15> = LockFreeRingBuffer::new();
    }
}
