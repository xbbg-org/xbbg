//! Three-session Engine for Bloomberg API.
//!
//! Architecture:
//! - Lane A (PumpA): Fast session for real-time subscriptions
//! - Lane B (PumpB): Slow session for bulk requests (bdp/bdh/bds)
//! - Lane C (PumpC): Slow session for intraday requests (bdib/bdtick)
//!
//! All pumps use slab-indexed correlation IDs for O(1) dispatch.
//! Lane C is separate from Lane B to prevent large intraday requests
//! from starving smaller bdp/bdh/bds requests.

mod pump_a;
mod pump_b;
mod pump_c;
pub mod state;

use std::sync::Arc;
use std::thread::JoinHandle;

use arrow::record_batch::RecordBatch;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::BlpError;

use crate::errors::BlpAsyncError;

pub use state::{OutputFormat, RequestState, SubscriptionState};

/// Slab key for O(1) correlation dispatch.
pub type SlabKey = usize;

/// Overflow policy for slow consumers.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum OverflowPolicy {
    /// Drop the newest data when buffer is full (default, non-blocking)
    #[default]
    DropNewest,
    /// Drop the oldest data when buffer is full (requires bounded ring buffer)
    DropOldest,
    /// Block the producer until space is available (use with caution)
    Block,
}

/// Commands sent to the Engine from the public API.
pub enum Command {
    // ─── Lane B: Bulk Requests ───────────────────────────────────────────────
    /// Reference data request (bdp)
    Bdp {
        tickers: Vec<String>,
        fields: Vec<String>,
        overrides: Vec<(String, String)>,
        format: OutputFormat,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Historical data request (bdh)
    Bdh {
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        options: Vec<(String, String)>,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Bulk data request (bds)
    Bds {
        ticker: String,
        field: String,
        overrides: Vec<(String, String)>,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },

    // ─── Lane C: Intraday Requests ────────────────────────────────────────────
    /// Intraday bar request (bdib)
    Bdib {
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Intraday tick request (bdtick)
    Bdtick {
        ticker: String,
        start_datetime: String,
        end_datetime: String,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },

    // ─── Streaming Variants ───────────────────────────────────────────────────
    /// Streaming historical data request
    BdhStream {
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        options: Vec<(String, String)>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Streaming intraday bar request
    BdibStream {
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Streaming intraday tick request
    BdtickStream {
        ticker: String,
        start_datetime: String,
        end_datetime: String,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    },

    // ─── Lane A: Subscriptions ───────────────────────────────────────────────
    /// Subscribe to real-time data
    Subscribe {
        topics: Vec<String>,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
    },
    /// Unsubscribe by slab keys
    Unsubscribe { keys: Vec<SlabKey> },

    // ─── Admin ───────────────────────────────────────────────────────────────
    /// Graceful shutdown
    Shutdown,
}

/// Configuration for the Engine.
pub struct EngineConfig {
    /// Server host (e.g., "localhost")
    pub server_host: String,
    /// Server port (e.g., 8194)
    pub server_port: u16,
    /// Max event queue size (Bloomberg SDK setting)
    pub max_event_queue_size: usize,
    /// Command channel capacity (backpressure)
    pub command_queue_size: usize,
    /// Subscription flush threshold (rows before auto-flush)
    pub subscription_flush_threshold: usize,
    /// Subscription stream capacity (backpressure)
    pub subscription_stream_capacity: usize,
    /// Overflow policy for slow consumers
    pub overflow_policy: OverflowPolicy,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            server_host: "localhost".to_string(),
            server_port: 8194,
            max_event_queue_size: 10_000,
            command_queue_size: 256,
            subscription_flush_threshold: 1000,
            subscription_stream_capacity: 256,
            overflow_policy: OverflowPolicy::default(),
        }
    }
}

impl Clone for EngineConfig {
    fn clone(&self) -> Self {
        Self {
            server_host: self.server_host.clone(),
            server_port: self.server_port,
            max_event_queue_size: self.max_event_queue_size,
            command_queue_size: self.command_queue_size,
            subscription_flush_threshold: self.subscription_flush_threshold,
            subscription_stream_capacity: self.subscription_stream_capacity,
            overflow_policy: self.overflow_policy,
        }
    }
}

/// Three-session Bloomberg Engine.
///
/// Owns three pump threads:
/// - Lane A (fast): subscriptions, real-time market data
/// - Lane B (slow): bulk requests (bdp/bdh/bds)
/// - Lane C (slow): intraday requests (bdib/bdtick)
pub struct Engine {
    /// Command channel to Lane A (subscriptions)
    cmd_a: mpsc::Sender<Command>,
    /// Command channel to Lane B (bulk requests)
    cmd_b: mpsc::Sender<Command>,
    /// Command channel to Lane C (intraday requests)
    cmd_c: mpsc::Sender<Command>,
    /// Pump thread handle for Lane A
    _pump_a: JoinHandle<()>,
    /// Pump thread handle for Lane B
    _pump_b: JoinHandle<()>,
    /// Pump thread handle for Lane C
    _pump_c: JoinHandle<()>,
    /// Tokio runtime for async ops
    rt: Arc<tokio::runtime::Runtime>,
}

impl Engine {
    /// Create and start a new Engine with three Bloomberg sessions.
    pub fn start(config: EngineConfig) -> Result<Self, BlpAsyncError> {
        let rt = Arc::new(
            tokio::runtime::Builder::new_multi_thread()
                .enable_all()
                .build()
                .map_err(|e| BlpAsyncError::Internal(format!("tokio runtime: {e}")))?,
        );

        // Create command channels with backpressure
        let (cmd_a_tx, cmd_a_rx) = mpsc::channel(config.command_queue_size);
        let (cmd_b_tx, cmd_b_rx) = mpsc::channel(config.command_queue_size);
        let (cmd_c_tx, cmd_c_rx) = mpsc::channel(config.command_queue_size);

        // Start Lane A (fast/subscriptions)
        let config_a = config.clone();
        let pump_a = std::thread::Builder::new()
            .name("blp-pump-a".into())
            .spawn(move || {
                if let Err(e) = pump_a::run(config_a, cmd_a_rx) {
                    tracing::error!("PumpA exited with error: {e:?}");
                }
            })
            .map_err(|e| BlpAsyncError::Internal(format!("spawn pump_a: {e}")))?;

        // Start Lane B (slow/bulk)
        let config_b = config.clone();
        let pump_b = std::thread::Builder::new()
            .name("blp-pump-b".into())
            .spawn(move || {
                if let Err(e) = pump_b::run(config_b, cmd_b_rx) {
                    tracing::error!("PumpB exited with error: {e:?}");
                }
            })
            .map_err(|e| BlpAsyncError::Internal(format!("spawn pump_b: {e}")))?;

        // Start Lane C (slow/intraday)
        let config_c = config.clone();
        let pump_c = std::thread::Builder::new()
            .name("blp-pump-c".into())
            .spawn(move || {
                if let Err(e) = pump_c::run(config_c, cmd_c_rx) {
                    tracing::error!("PumpC exited with error: {e:?}");
                }
            })
            .map_err(|e| BlpAsyncError::Internal(format!("spawn pump_c: {e}")))?;

        Ok(Self {
            cmd_a: cmd_a_tx,
            cmd_b: cmd_b_tx,
            cmd_c: cmd_c_tx,
            _pump_a: pump_a,
            _pump_b: pump_b,
            _pump_c: pump_c,
            rt,
        })
    }

    /// Reference data (bdp) - routes to Lane B.
    /// Uses Long format (one row per ticker-field pair) by default.
    pub async fn bdp(
        &self,
        tickers: Vec<String>,
        fields: Vec<String>,
        overrides: Vec<(String, String)>,
    ) -> Result<RecordBatch, BlpAsyncError> {
        self.bdp_with_format(tickers, fields, overrides, OutputFormat::Long)
            .await
    }

    /// Reference data (bdp) with format selection - routes to Lane B.
    pub async fn bdp_with_format(
        &self,
        tickers: Vec<String>,
        fields: Vec<String>,
        overrides: Vec<(String, String)>,
        format: OutputFormat,
    ) -> Result<RecordBatch, BlpAsyncError> {
        let (tx, rx) = oneshot::channel();
        self.cmd_b
            .send(Command::Bdp {
                tickers,
                fields,
                overrides,
                format,
                reply: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        rx.await
            .map_err(|_| BlpAsyncError::Internal("reply dropped".into()))?
            .map_err(|e| BlpAsyncError::Internal(e.to_string()))
    }

    /// Historical data (bdh) - routes to Lane B.
    pub async fn bdh(
        &self,
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        options: Vec<(String, String)>,
    ) -> Result<RecordBatch, BlpAsyncError> {
        let (tx, rx) = oneshot::channel();
        self.cmd_b
            .send(Command::Bdh {
                tickers,
                fields,
                start_date,
                end_date,
                options,
                reply: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        rx.await
            .map_err(|_| BlpAsyncError::Internal("reply dropped".into()))?
            .map_err(|e| BlpAsyncError::Internal(e.to_string()))
    }

    /// Bulk data (bds) - routes to Lane B.
    pub async fn bds(
        &self,
        ticker: String,
        field: String,
        overrides: Vec<(String, String)>,
    ) -> Result<RecordBatch, BlpAsyncError> {
        let (tx, rx) = oneshot::channel();
        self.cmd_b
            .send(Command::Bds {
                ticker,
                field,
                overrides,
                reply: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        rx.await
            .map_err(|_| BlpAsyncError::Internal("reply dropped".into()))?
            .map_err(|e| BlpAsyncError::Internal(e.to_string()))
    }

    /// Intraday bars (bdib) - routes to Lane C.
    pub async fn bdib(
        &self,
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
    ) -> Result<RecordBatch, BlpAsyncError> {
        let (tx, rx) = oneshot::channel();
        self.cmd_c
            .send(Command::Bdib {
                ticker,
                event_type,
                interval,
                start_datetime,
                end_datetime,
                reply: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        rx.await
            .map_err(|_| BlpAsyncError::Internal("reply dropped".into()))?
            .map_err(|e| BlpAsyncError::Internal(e.to_string()))
    }

    /// Intraday ticks (bdtick) - routes to Lane C.
    pub async fn bdtick(
        &self,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
    ) -> Result<RecordBatch, BlpAsyncError> {
        let (tx, rx) = oneshot::channel();
        self.cmd_c
            .send(Command::Bdtick {
                ticker,
                start_datetime,
                end_datetime,
                reply: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        rx.await
            .map_err(|_| BlpAsyncError::Internal("reply dropped".into()))?
            .map_err(|e| BlpAsyncError::Internal(e.to_string()))
    }

    // ─── Streaming Variants ───────────────────────────────────────────────────

    /// Streaming historical data (bdh_stream) - routes to Lane B.
    /// Returns a receiver that yields RecordBatch chunks as they arrive.
    pub async fn bdh_stream(
        &self,
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        options: Vec<(String, String)>,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(256);
        self.cmd_b
            .send(Command::BdhStream {
                tickers,
                fields,
                start_date,
                end_date,
                options,
                stream: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(rx)
    }

    /// Streaming intraday bars (bdib_stream) - routes to Lane C.
    /// Returns a receiver that yields RecordBatch chunks as they arrive.
    pub async fn bdib_stream(
        &self,
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(256);
        self.cmd_c
            .send(Command::BdibStream {
                ticker,
                event_type,
                interval,
                start_datetime,
                end_datetime,
                stream: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(rx)
    }

    /// Streaming intraday ticks (bdtick_stream) - routes to Lane C.
    /// Returns a receiver that yields RecordBatch chunks as they arrive.
    pub async fn bdtick_stream(
        &self,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(256);
        self.cmd_c
            .send(Command::BdtickStream {
                ticker,
                start_datetime,
                end_datetime,
                stream: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(rx)
    }

    /// Subscribe to real-time data - routes to Lane A.
    pub async fn subscribe(
        &self,
        topics: Vec<String>,
        fields: Vec<String>,
    ) -> Result<mpsc::Receiver<RecordBatch>, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(256);
        self.cmd_a
            .send(Command::Subscribe {
                topics,
                fields,
                stream: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(rx)
    }

    /// Unsubscribe by slab keys - routes to Lane A.
    pub async fn unsubscribe(&self, keys: Vec<SlabKey>) -> Result<(), BlpAsyncError> {
        self.cmd_a
            .send(Command::Unsubscribe { keys })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(())
    }

    /// Graceful shutdown of all sessions.
    pub async fn shutdown(self) -> Result<(), BlpAsyncError> {
        // Send shutdown to all lanes
        let _ = self.cmd_a.send(Command::Shutdown).await;
        let _ = self.cmd_b.send(Command::Shutdown).await;
        let _ = self.cmd_c.send(Command::Shutdown).await;
        Ok(())
    }

    /// Get the tokio runtime (for spawning tasks).
    pub fn runtime(&self) -> &Arc<tokio::runtime::Runtime> {
        &self.rt
    }
}
