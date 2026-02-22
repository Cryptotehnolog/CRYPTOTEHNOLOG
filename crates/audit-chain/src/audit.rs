// ==================== CRYPTOTEHNOLOG Audit Chain ====================
// Immutable audit chain for regulatory compliance
//
// Features:
// - Cryptographic linking between records (hash chain)
// - Immutable audit trail
// - Verifiable integrity
// - SEC/MiFID II/SOX compliance ready

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Audit chain for immutable record keeping
#[derive(Debug, Clone)]
pub struct AuditChain {
    /// In-memory records
    records: Arc<RwLock<Vec<AuditRecord>>>,
    /// Current root hash
    current_hash: Arc<RwLock<String>>,
}

impl Default for AuditChain {
    fn default() -> Self {
        Self::new()
    }
}

impl AuditChain {
    /// Create a new audit chain
    pub fn new() -> Self {
        Self {
            records: Arc::new(RwLock::new(Vec::new())),
            current_hash: Arc::new(RwLock::new("0".repeat(64))),
        }
    }

    /// Append a new audit record to the chain
    ///
    /// This method creates a cryptographically linked record
    /// with hash of previous record for tamper-proof audit trail.
    pub async fn append(
        &self,
        event_type: impl Into<String>,
        data: serde_json::Value,
    ) -> Result<AuditRecord, AuditError> {
        let event_type = event_type.into();
        let timestamp = chrono::Utc::now();
        let id = uuid::Uuid::new_v4();

        // Get previous hash
        let previous_hash = {
            let current_hash = self.current_hash.read().await;
            current_hash.clone()
        };

        // Create record hash
        let record_hash = Self::compute_hash(&id, &timestamp, &event_type, &data, &previous_hash);

        // Create record
        let record = AuditRecord {
            id,
            timestamp,
            event_type,
            data,
            previous_hash,
            hash: hex::encode(record_hash),
        };

        // Append to chain
        let mut records = self.records.write().await;
        records.push(record.clone());

        // Update current hash
        let mut current_hash = self.current_hash.write().await;
        *current_hash = record.hash.clone();
        drop(current_hash);

        Ok(record)
    }

    /// Get all records in the chain
    pub async fn get_all_records(&self) -> Vec<AuditRecord> {
        let records = self.records.read().await;
        records.clone()
    }

    /// Get records by event type
    pub async fn get_records_by_type(&self, event_type: &str) -> Vec<AuditRecord> {
        let records = self.records.read().await;
        records
            .iter()
            .filter(|r| r.event_type == event_type)
            .cloned()
            .collect()
    }

    /// Get records in time range
    pub async fn get_records_by_time_range(
        &self,
        start: chrono::DateTime<chrono::Utc>,
        end: chrono::DateTime<chrono::Utc>,
    ) -> Vec<AuditRecord> {
        let records = self.records.read().await;
        records
            .iter()
            .filter(|r| r.timestamp >= start && r.timestamp <= end)
            .cloned()
            .collect()
    }

    /// Verify chain integrity
    ///
    /// Returns true if all records are properly linked
    pub async fn verify_integrity(&self) -> bool {
        let records = self.records.read().await;

        if records.is_empty() {
            return true;
        }

        // Verify each record links to previous
        for (i, record) in records.iter().enumerate() {
            if i == 0 {
                // First record should have "0" as previous hash
                if record.previous_hash != "0".repeat(64) {
                    return false;
                }
            } else {
                // Verify previous hash matches
                let prev_record = &records[i - 1];
                if record.previous_hash != prev_record.hash {
                    return false;
                }
            }

            // Verify current hash is correct
            let expected_hash = Self::compute_hash(
                &record.id,
                &record.timestamp,
                &record.event_type,
                &record.data,
                &record.previous_hash,
            );

            let expected_hex = hex::encode(expected_hash);
            if record.hash != expected_hex {
                return false;
            }
        }

        true
    }

    /// Get the number of records in the chain
    pub async fn len(&self) -> usize {
        let records = self.records.read().await;
        records.len()
    }

    /// Check if the chain is empty
    pub async fn is_empty(&self) -> bool {
        self.len().await == 0
    }

    /// Get current root hash
    pub async fn current_hash(&self) -> String {
        let current_hash = self.current_hash.read().await;
        current_hash.clone()
    }

    /// Compute hash for a record
    fn compute_hash(
        id: &uuid::Uuid,
        timestamp: &chrono::DateTime<chrono::Utc>,
        event_type: &str,
        data: &serde_json::Value,
        previous_hash: &str,
    ) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(id.as_bytes());
        hasher.update(timestamp.to_rfc3339().as_bytes());
        hasher.update(event_type.as_bytes());
        hasher.update(data.to_string().as_bytes());
        hasher.update(previous_hash.as_bytes());
        hasher.finalize().into()
    }
}

/// Audit record in the chain
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditRecord {
    /// Record ID
    pub id: uuid::Uuid,
    /// Timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
    /// Event type
    pub event_type: String,
    /// Event data
    pub data: serde_json::Value,
    /// Previous hash (for chain linking)
    pub previous_hash: String,
    /// Current hash
    pub hash: String,
}

/// Audit error types
#[derive(Debug, thiserror::Error)]
pub enum AuditError {
    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("Invalid record format: {0}")]
    InvalidFormat(String),
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_audit_chain_creation() {
        let chain = AuditChain::new();
        assert!(chain.is_empty().await);
        assert_eq!(chain.len().await, 0);
    }

    #[tokio::test]
    async fn test_append_record() {
        let chain = AuditChain::new();

        let record = chain
            .append("TEST_EVENT", serde_json::json!({"key": "value"}))
            .await
            .unwrap();

        assert_eq!(record.event_type, "TEST_EVENT");
        assert_eq!(chain.len().await, 1);
    }

    #[tokio::test]
    async fn test_chain_linking() {
        let chain = AuditChain::new();

        let record1 = chain
            .append("EVENT_1", serde_json::json!({"seq": 1}))
            .await
            .unwrap();

        let record2 = chain
            .append("EVENT_2", serde_json::json!({"seq": 2}))
            .await
            .unwrap();

        // Verify linking
        assert_eq!(record1.previous_hash, "0".repeat(64));
        assert_eq!(record2.previous_hash, record1.hash);
    }

    #[tokio::test]
    async fn test_integrity_verification() {
        let chain = AuditChain::new();

        chain
            .append("EVENT_1", serde_json::json!({"seq": 1}))
            .await
            .unwrap();
        chain
            .append("EVENT_2", serde_json::json!({"seq": 2}))
            .await
            .unwrap();
        chain
            .append("EVENT_3", serde_json::json!({"seq": 3}))
            .await
            .unwrap();

        assert!(chain.verify_integrity().await);
    }

    #[tokio::test]
    async fn test_get_records_by_type() {
        let chain = AuditChain::new();

        chain
            .append("POSITION_UPDATE", serde_json::json!({"id": "1"}))
            .await
            .unwrap();
        chain
            .append("RISK_CHECK", serde_json::json!({"passed": true}))
            .await
            .unwrap();
        chain
            .append("POSITION_UPDATE", serde_json::json!({"id": "2"}))
            .await
            .unwrap();

        let position_updates = chain.get_records_by_type("POSITION_UPDATE").await;
        assert_eq!(position_updates.len(), 2);

        let risk_checks = chain.get_records_by_type("RISK_CHECK").await;
        assert_eq!(risk_checks.len(), 1);
    }

    #[tokio::test]
    async fn test_current_hash() {
        let chain = AuditChain::new();

        let hash1 = chain.current_hash().await;
        assert_eq!(hash1, "0".repeat(64));

        chain
            .append("EVENT_1", serde_json::json!({}))
            .await
            .unwrap();

        let hash2 = chain.current_hash().await;
        assert_ne!(hash2, "0".repeat(64));
    }
}
