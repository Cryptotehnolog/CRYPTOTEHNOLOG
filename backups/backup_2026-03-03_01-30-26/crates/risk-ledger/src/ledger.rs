// ==================== CRYPTOTEHNOLOG Risk Ledger ====================
// Main risk ledger combining WAL, Merkle tree, and double-entry validation
//
// The Risk Ledger provides:
// - Append-only operations
// - WAL for durability
// - Merkle tree for integrity
// - Double-entry validation for consistency
// - O(log n) proof generation and verification

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, instrument};

use super::merkle::MerkleTree;
use super::validation::{DoubleEntryValidator, Transaction};
use super::wal::WriteAheadLog;
use cryptotechnolog_audit_chain::AuditChain;

/// Position in the risk ledger
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    /// Position identifier
    pub id: String,
    /// Symbol (e.g., "BTC/USDT")
    pub symbol: String,
    /// Position size (positive for long, negative for short)
    pub size: f64,
    /// Entry price
    pub entry_price: f64,
    /// Current price
    pub current_price: f64,
    /// Unrealized PnL
    pub unrealized_pnl: f64,
    /// Position timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

impl Position {
    /// Calculate unrealized PnL
    pub fn calculate_pnl(&self) -> f64 {
        if self.size > 0.0 {
            // Long position
            (self.current_price - self.entry_price) * self.size
        } else {
            // Short position
            (self.entry_price - self.current_price) * self.size.abs()
        }
    }

    /// Update current price and recalculate PnL
    pub fn update_price(&mut self, price: f64) {
        self.current_price = price;
        self.unrealized_pnl = self.calculate_pnl();
    }
}

/// Risk ledger combining WAL, Merkle tree, and validation
pub struct RiskLedger {
    /// Write-ahead log
    wal: Arc<RwLock<WriteAheadLog>>,
    /// Positions by ID
    positions: Arc<RwLock<HashMap<String, Position>>>,
    /// Merkle tree for integrity
    merkle: Arc<RwLock<MerkleTree>>,
    /// Validator for double-entry
    validator: DoubleEntryValidator,
    /// Audit chain for immutable record keeping
    audit: AuditChain,
    /// WAL file path
    wal_path: PathBuf,
}

impl RiskLedger {
    /// Create a new risk ledger
    pub async fn new(wal_path: PathBuf) -> Result<Self, Box<dyn std::error::Error>> {
        let wal = WriteAheadLog::new(wal_path.clone()).await?;
        let wal = Arc::new(RwLock::new(wal));

        let positions = Arc::new(RwLock::new(HashMap::new()));
        let merkle = Arc::new(RwLock::new(MerkleTree::from_leaves(vec![])));
        let validator = DoubleEntryValidator::new();
        let audit = AuditChain::new();

        Ok(Self {
            wal,
            positions,
            merkle,
            validator,
            audit,
            wal_path,
        })
    }

    /// Add or update a position
    #[instrument(skip(self, position), fields(position_id = %position.id, symbol = %position.symbol))]
    pub async fn update_position(
        &self,
        position: Position,
    ) -> Result<(), Box<dyn std::error::Error>> {
        info!("Updating position");

        // Create transactions for double-entry validation
        let transactions = vec![
            Transaction::new(position.id.clone(), position.size),
            Transaction::new("RISK_LEDGER".to_string(), -position.size),
        ];

        // Validate double-entry
        self.validator.validate(&transactions)?;

        // Append to WAL
        let data = serde_json::to_value(&position)?;
        let mut wal = self.wal.write().await;
        wal.append("UPDATE_POSITION".to_string(), data.clone())
            .await?;
        wal.flush().await?;
        drop(wal);

        // Append to audit chain
        self.audit
            .append(
                "POSITION_UPDATE",
                serde_json::json!({
                    "position_id": position.id,
                    "symbol": position.symbol,
                    "size": position.size,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "unrealized_pnl": position.unrealized_pnl,
                    "timestamp": position.timestamp,
                }),
            )
            .await?;

        // Update in-memory state
        let mut positions = self.positions.write().await;
        positions.insert(position.id.clone(), position.clone());
        drop(positions);

        // Update Merkle tree
        self.update_merkle().await?;

        info!(position_id = %position.id, "Position updated successfully");
        Ok(())
    }

    /// Get a position by ID
    pub async fn get_position(&self, id: &str) -> Option<Position> {
        let positions = self.positions.read().await;
        positions.get(id).cloned()
    }

    /// Get all positions
    pub async fn get_all_positions(&self) -> Vec<Position> {
        let positions = self.positions.read().await;
        positions.values().cloned().collect()
    }

    /// Calculate total portfolio value
    pub async fn calculate_portfolio_value(&self) -> f64 {
        let positions = self.positions.read().await;
        positions
            .values()
            .map(|p| p.current_price * p.size.abs())
            .sum()
    }

    /// Calculate total unrealized PnL
    pub async fn calculate_total_pnl(&self) -> f64 {
        let positions = self.positions.read().await;
        positions.values().map(|p| p.unrealized_pnl).sum()
    }

    /// Get Merkle root
    pub async fn merkle_root(&self) -> [u8; 32] {
        let merkle: tokio::sync::RwLockReadGuard<'_, MerkleTree> = self.merkle.read().await;
        merkle.root()
    }

    /// Generate Merkle proof for a position
    pub async fn generate_proof(&self, position_id: &str) -> Option<super::merkle::MerkleProof> {
        let positions = self.positions.read().await;
        let position_ids: Vec<String> = positions.keys().cloned().collect();
        let index = position_ids.iter().position(|id| id == position_id)?;
        drop(positions);

        let merkle: tokio::sync::RwLockReadGuard<'_, MerkleTree> = self.merkle.read().await;
        merkle.generate_proof(index)
    }

    /// Verify Merkle proof for a position
    pub async fn verify_proof(
        &self,
        position_id: &str,
        proof: &super::merkle::MerkleProof,
    ) -> bool {
        let positions = self.positions.read().await;

        if let Some(position) = positions.get(position_id) {
            let leaf_hash = Self::hash_position(position);
            drop(positions);
            let merkle: tokio::sync::RwLockReadGuard<'_, MerkleTree> = self.merkle.read().await;
            merkle.verify(&leaf_hash, proof)
        } else {
            false
        }
    }

    /// Replay WAL to recover state
    pub async fn replay_wal(&self) -> Result<Vec<Position>, Box<dyn std::error::Error>> {
        // Use static method to read WAL without opening for writing
        // This avoids file locking issues on Windows
        let entries = WriteAheadLog::replay_from_file(&self.wal_path).await?;

        let mut recovered_positions = Vec::new();

        for entry in entries {
            if entry.operation == "UPDATE_POSITION" {
                if let Ok(position) = serde_json::from_value::<Position>(entry.data) {
                    recovered_positions.push(position);
                }
            }
        }

        // Update in-memory state
        let mut positions = self.positions.write().await;
        for position in recovered_positions.iter() {
            positions.insert(position.id.clone(), position.clone());
        }
        drop(positions);

        // Update Merkle tree
        self.update_merkle().await?;

        Ok(recovered_positions)
    }

    /// Close the risk ledger (flush WAL)
    pub async fn close(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut wal = self.wal.write().await;
        wal.flush().await?;
        drop(wal);
        Ok(())
    }

    /// Get the WAL file path
    pub fn wal_path(&self) -> &PathBuf {
        &self.wal_path
    }

    /// Close WAL (for recovery or cleanup)
    pub async fn close_wal(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut wal = self.wal.write().await;
        wal.close().await
    }

    /// Reopen WAL (after close)
    pub async fn reopen_wal(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut wal = self.wal.write().await;
        wal.reopen().await
    }

    /// Get audit records by position ID
    pub async fn get_audit_records_for_position(
        &self,
        position_id: &str,
    ) -> Vec<cryptotechnolog_audit_chain::AuditRecord> {
        let all_records: Vec<cryptotechnolog_audit_chain::AuditRecord> =
            self.audit.get_all_records().await;
        all_records
            .into_iter()
            .filter(|r: &cryptotechnolog_audit_chain::AuditRecord| {
                r.data
                    .get("position_id")
                    .and_then(|v: &serde_json::Value| v.as_str())
                    .map(|id| id == position_id)
                    .unwrap_or(false)
            })
            .collect()
    }

    /// Get all audit records
    pub async fn get_all_audit_records(&self) -> Vec<cryptotechnolog_audit_chain::AuditRecord> {
        self.audit.get_all_records().await
    }

    /// Verify audit chain integrity
    pub async fn verify_audit_integrity(&self) -> bool {
        self.audit.verify_integrity().await
    }

    /// Get audit chain current hash
    pub async fn audit_hash(&self) -> String {
        self.audit.current_hash().await
    }

    /// Update Merkle tree with current positions
    async fn update_merkle(&self) -> Result<(), Box<dyn std::error::Error>> {
        let positions = self.positions.read().await;
        let leaves: Vec<[u8; 32]> = positions.values().map(Self::hash_position).collect();
        drop(positions);

        let mut merkle = self.merkle.write().await;
        *merkle = MerkleTree::from_leaves(leaves);
        drop(merkle);

        Ok(())
    }

    /// Hash a position for Merkle tree
    fn hash_position(position: &Position) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(position.id.as_bytes());
        hasher.update(position.symbol.as_bytes());
        hasher.update(position.size.to_le_bytes());
        hasher.update(position.entry_price.to_le_bytes());
        hasher.update(position.current_price.to_le_bytes());
        hasher.finalize().into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_risk_ledger_creation() {
        let path = PathBuf::from("test_risk_ledger_wal.log");
        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        assert_eq!(ledger.calculate_portfolio_value().await, 0.0);
        assert_eq!(ledger.calculate_total_pnl().await, 0.0);

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_update_position() {
        let path = PathBuf::from("test_risk_ledger_update.log");
        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        let position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        ledger.update_position(position.clone()).await.unwrap();

        let retrieved = ledger.get_position("BTC/USDT-1").await.unwrap();
        assert_eq!(retrieved.id, "BTC/USDT-1");
        assert_eq!(retrieved.size, 100.0);

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_portfolio_calculation() {
        let path = PathBuf::from("test_risk_ledger_portfolio.log");
        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        let position1 = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        let position2 = Position {
            id: "ETH/USDT-1".to_string(),
            symbol: "ETH/USDT".to_string(),
            size: 1000.0,
            entry_price: 3000.0,
            current_price: 3100.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        ledger.update_position(position1).await.unwrap();
        ledger.update_position(position2).await.unwrap();

        let value = ledger.calculate_portfolio_value().await;
        assert_eq!(value, 5100000.0 + 3100000.0);

        let pnl = ledger.calculate_total_pnl().await;
        assert_eq!(pnl, 200000.0);

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_merkle_proof() {
        let path = PathBuf::from("test_risk_ledger_merkle.log");
        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        let position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        ledger.update_position(position.clone()).await.unwrap();

        let proof = ledger.generate_proof("BTC/USDT-1").await.unwrap();
        assert!(proof.leaf_hash != [0u8; 32]);

        let verified = ledger.verify_proof("BTC/USDT-1", &proof).await;
        assert!(verified);

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_wal_replay() {
        let path = PathBuf::from("test_risk_ledger_replay.log");

        // Clean up old test file if exists
        tokio::fs::remove_file(&path).await.ok();

        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        let position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        // Write position to WAL
        ledger.update_position(position.clone()).await.unwrap();

        // Flush and close WAL before replay (required on Windows to release file lock)
        ledger.close_wal().await.unwrap();

        // Replay WAL (simulating recovery after crash)
        let recovered = ledger.replay_wal().await.unwrap();

        assert_eq!(recovered.len(), 1);
        assert_eq!(recovered[0].id, "BTC/USDT-1");

        // Reopen WAL for continued operations
        ledger.reopen_wal().await.unwrap();

        // Verify we can still write after reopening
        let position2 = Position {
            id: "ETH/USDT-1".to_string(),
            symbol: "ETH/USDT".to_string(),
            size: 500.0,
            entry_price: 3000.0,
            current_price: 3100.0,
            unrealized_pnl: 50000.0,
            timestamp: chrono::Utc::now(),
        };

        ledger.update_position(position2).await.unwrap();

        let retrieved = ledger.get_position("ETH/USDT-1").await.unwrap();
        assert_eq!(retrieved.id, "ETH/USDT-1");

        // Cleanup
        ledger.close().await.unwrap();
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_audit_integration() {
        let path = PathBuf::from("test_risk_ledger_audit.log");
        tokio::fs::remove_file(&path).await.ok();

        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        let position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        // Update position - should create audit record
        ledger.update_position(position.clone()).await.unwrap();

        // Get audit records for this position
        let audit_records = ledger.get_audit_records_for_position("BTC/USDT-1").await;

        assert_eq!(audit_records.len(), 1);
        assert_eq!(audit_records[0].event_type, "POSITION_UPDATE");

        // Verify audit integrity
        assert!(ledger.verify_audit_integrity().await);

        // Check audit hash is not zero
        let audit_hash = ledger.audit_hash().await;
        assert_ne!(audit_hash, "0".repeat(64));

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }

    #[tokio::test]
    async fn test_audit_multiple_updates() {
        let path = PathBuf::from("test_risk_ledger_audit_multi.log");
        tokio::fs::remove_file(&path).await.ok();

        let ledger = RiskLedger::new(path.clone()).await.unwrap();

        let mut position = Position {
            id: "BTC/USDT-1".to_string(),
            symbol: "BTC/USDT".to_string(),
            size: 100.0,
            entry_price: 50000.0,
            current_price: 51000.0,
            unrealized_pnl: 100000.0,
            timestamp: chrono::Utc::now(),
        };

        // Update position multiple times
        for i in 1..=3 {
            position.current_price = 50000.0 + (i as f64) * 1000.0;
            position.unrealized_pnl = position.calculate_pnl();
            ledger.update_position(position.clone()).await.unwrap();
        }

        // Should have 3 audit records
        let audit_records = ledger.get_audit_records_for_position("BTC/USDT-1").await;

        assert_eq!(audit_records.len(), 3);

        // Verify chain linking
        assert_eq!(audit_records[0].previous_hash, "0".repeat(64));
        assert_eq!(audit_records[1].previous_hash, audit_records[0].hash);
        assert_eq!(audit_records[2].previous_hash, audit_records[1].hash);

        // Cleanup
        tokio::fs::remove_file(path).await.ok();
    }
}
