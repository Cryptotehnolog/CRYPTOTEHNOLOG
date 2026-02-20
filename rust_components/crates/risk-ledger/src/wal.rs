// ==================== CRYPTOTEHNOLOG Risk Ledger WAL ====================
// Write-Ahead Log for durable risk ledger operations
//
// The WAL provides:
// - Append-only log of all operations
// - Crash recovery capability
// - Durability guarantees
// - Sequential writes for performance
// - Concurrent read/write support on Windows via proper file sharing modes

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::File as StdFile;
use std::io::Write;
use std::path::PathBuf;

#[cfg(windows)]
use std::os::windows::fs::OpenOptionsExt;
#[cfg(windows)]
use winapi::um::winnt::FILE_SHARE_READ;

/// WAL entry representing a single operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WALEntry {
    /// Entry sequence number
    pub sequence: u64,
    /// Entry timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
    /// Operation type
    pub operation: String,
    /// Entry data (JSON)
    pub data: serde_json::Value,
    /// Entry hash for integrity
    pub hash: String,
}

impl WALEntry {
    /// Create a new WAL entry
    pub fn new(sequence: u64, operation: String, data: serde_json::Value) -> Self {
        let timestamp = chrono::Utc::now();
        let hash = Self::compute_hash(&sequence, &timestamp, &operation, &data);

        Self {
            sequence,
            timestamp,
            operation,
            data,
            hash,
        }
    }

    /// Compute hash for the entry
    fn compute_hash(
        sequence: &u64,
        timestamp: &chrono::DateTime<chrono::Utc>,
        operation: &str,
        data: &serde_json::Value,
    ) -> String {
        let mut hasher = Sha256::new();
        hasher.update(sequence.to_le_bytes());
        hasher.update(timestamp.to_rfc3339().as_bytes());
        hasher.update(operation.as_bytes());
        hasher.update(data.to_string().as_bytes());

        hex::encode(hasher.finalize())
    }

    /// Verify entry hash
    pub fn verify(&self) -> bool {
        let computed_hash = Self::compute_hash(&self.sequence, &self.timestamp, &self.operation, &self.data);
        computed_hash == self.hash
    }
}

/// Write-Ahead Log for risk ledger operations
pub struct WriteAheadLog {
    /// Path to WAL file
    path: PathBuf,
    /// Current sequence number
    sequence: u64,
    /// File writer (use std::fs for better Windows compatibility)
    writer: std::io::BufWriter<StdFile>,
}

impl WriteAheadLog {
    /// Create a new WAL with proper file sharing modes for concurrent read/write
    pub async fn new(path: PathBuf) -> Result<Self, Box<dyn std::error::Error>> {
        // Open file with appropriate sharing modes
        // Windows: FILE_SHARE_READ allows concurrent reads while writing
        // Linux/Mac: Default behavior already allows concurrent access
        let file = if cfg!(windows) {
            // Use std::fs::File with explicit share modes for Windows
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .share_mode(FILE_SHARE_READ)  // Allow concurrent reads
                .open(&path)?
        } else {
            // Use std::fs::File on Linux/Mac as well (simpler, works for append-only)
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&path)?
        };

        let writer = std::io::BufWriter::new(file);

        Ok(Self {
            path,
            sequence: 0,
            writer,
        })
    }

    /// Append an entry to the WAL
    pub async fn append(&mut self, operation: String, data: serde_json::Value) -> Result<WALEntry, Box<dyn std::error::Error>> {
        let entry = WALEntry::new(self.sequence, operation, data);

        // Serialize entry
        let serialized = serde_json::to_string(&entry)?;
        let bytes = serialized.as_bytes();

        // Write to file (synchronous - no .await)
        self.writer.write_all(bytes)?;
        self.writer.write_all(b"\n")?;
        self.writer.flush()?;

        // Increment sequence
        self.sequence += 1;

        Ok(entry)
    }

    /// Replay WAL from file with concurrent read support
    ///
    /// This method reads all entries from the WAL file without closing the writer.
    /// On Windows, we use FILE_SHARE_READ to allow concurrent reading while the
    /// writer is still open. On Linux/Mac, concurrent access is allowed by default.
    ///
    /// Returns all entries in the WAL in the order they were written.
    pub async fn replay(&self) -> Result<Vec<WALEntry>, Box<dyn std::error::Error>> {
        // Use synchronous file reading (works on all platforms with FILE_SHARE_READ)
        let contents = std::fs::read_to_string(&self.path)?;

        let mut entries = Vec::new();

        for line in contents.lines() {
            if line.is_empty() {
                continue;
            }

            match serde_json::from_str::<WALEntry>(line) {
                Ok(entry) => entries.push(entry),
                Err(e) => {
                    // Log warning but continue - corrupted entry shouldn't fail replay
                    eprintln!("Warning: Failed to parse WAL entry: {}", e);
                }
            }
        }

        Ok(entries)
    }

    /// Replay WAL from file path (static method, doesn't open file for writing)
    ///
    /// This is useful for recovery scenarios where you want to read the WAL
    /// without opening it for writing. On Windows, this avoids file locking issues.
    ///
    /// Args:
    ///   path: Path to the WAL file
    ///
    /// Returns all entries in the WAL in the order they were written.
    pub async fn replay_from_file(path: &PathBuf) -> Result<Vec<WALEntry>, Box<dyn std::error::Error>> {
        // Use synchronous file reading
        let contents = std::fs::read_to_string(path)?;

        let mut entries = Vec::new();

        for line in contents.lines() {
            if line.is_empty() {
                continue;
            }

            match serde_json::from_str::<WALEntry>(line) {
                Ok(entry) => entries.push(entry),
                Err(e) => {
                    // Log warning but continue - corrupted entry shouldn't fail replay
                    eprintln!("Warning: Failed to parse WAL entry: {}", e);
                }
            }
        }

        Ok(entries)
    }

    /// Get current sequence number
    pub fn sequence(&self) -> u64 {
        self.sequence
    }

    /// Flush WAL to disk
    pub async fn flush(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        self.writer.flush()?;
        Ok(())
    }

    /// Truncate WAL (for cleanup)
    pub async fn truncate(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        // Flush current writer
        self.writer.flush()?;

        // Truncate file
        std::fs::write(&self.path, b"")?;

        // Replace writer with new one with proper sharing modes
        let file = if cfg!(windows) {
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .share_mode(FILE_SHARE_READ)
                .open(&self.path)?
        } else {
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.path)?
        };

        self.writer = std::io::BufWriter::new(file);
        self.sequence = 0;

        Ok(())
    }

    /// Close the WAL (release file handle)
    pub async fn close(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        self.writer.flush()?;
        let _ = std::mem::replace(&mut self.writer, std::io::BufWriter::new(std::fs::File::open("NUL")?));
        Ok(())
    }

    /// Reopen the WAL (after close)
    pub async fn reopen(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let file = if cfg!(windows) {
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .share_mode(FILE_SHARE_READ)
                .open(&self.path)?
        } else {
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.path)?
        };

        self.writer = std::io::BufWriter::new(file);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_wal_entry_creation() {
        let data = serde_json::json!({"position": "BTC/USDT", "size": 100.0});
        let entry = WALEntry::new(0, "UPDATE_POSITION".to_string(), data);

        assert_eq!(entry.sequence, 0);
        assert_eq!(entry.operation, "UPDATE_POSITION");
        assert!(entry.verify());
    }

    #[tokio::test]
    async fn test_wal_append_and_replay() {
        let path = PathBuf::from("test_wal.log");

        // Cleanup old test file if exists
        tokio::fs::remove_file(&path).await.ok();

        // Create WAL
        let mut wal = WriteAheadLog::new(path.clone()).await.unwrap();

        // Append entry
        let data = serde_json::json!({"position": "BTC/USDT", "size": 100.0});
        let entry = wal.append("UPDATE_POSITION".to_string(), data).await.unwrap();

        assert_eq!(entry.sequence, 0);

        // Replay WAL
        let entries = wal.replay().await.unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].sequence, 0);

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_wal_multiple_entries() {
        let path = PathBuf::from("test_wal_multi.log");

        // Cleanup old test file if exists
        tokio::fs::remove_file(&path).await.ok();

        let mut wal = WriteAheadLog::new(path.clone()).await.unwrap();

        // Append multiple entries
        for i in 0..5 {
            let data = serde_json::json!({"index": i});
            wal.append("TEST".to_string(), data).await.unwrap();
        }

        // Replay
        let entries = wal.replay().await.unwrap();
        assert_eq!(entries.len(), 5);

        // Verify sequence numbers
        for (i, entry) in entries.iter().enumerate() {
            assert_eq!(entry.sequence, i as u64);
        }

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }
}
