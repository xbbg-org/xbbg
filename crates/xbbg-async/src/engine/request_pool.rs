//! Request worker pool with round-robin dispatch.
//!
//! The pool manages a collection of pre-warmed workers and distributes
//! incoming requests across them using round-robin scheduling.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use arrow::record_batch::RecordBatch;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::BlpError;

use super::worker::{WorkerCommand, WorkerHandle};
use super::{BlpAsyncError, EngineConfig, RequestParams};

/// Pool of request workers with round-robin dispatch.
pub struct RequestWorkerPool {
    /// Worker handles.
    workers: Vec<WorkerHandle>,
    /// Round-robin counter.
    next_worker: AtomicUsize,
    /// Configuration.
    #[allow(dead_code)]
    config: Arc<EngineConfig>,
}

impl RequestWorkerPool {
    /// Create a new pool with the specified number of workers.
    ///
    /// Each worker is spawned on a dedicated thread with a pre-warmed
    /// Bloomberg session.
    pub fn new(size: usize, config: Arc<EngineConfig>) -> Result<Self, BlpAsyncError> {
        if size == 0 {
            return Err(BlpAsyncError::ConfigError {
                detail: "request_pool_size must be at least 1".to_string(),
            });
        }

        tracing::info!(pool_size = size, "creating request worker pool");

        let mut workers = Vec::with_capacity(size);
        for id in 0..size {
            let handle = WorkerHandle::spawn(id, config.clone()).map_err(|e| {
                BlpAsyncError::BlpError(BlpError::Internal {
                    detail: format!("failed to spawn worker {}: {}", id, e),
                })
            })?;
            workers.push(handle);
        }

        tracing::info!(pool_size = size, "request worker pool ready");

        Ok(Self {
            workers,
            next_worker: AtomicUsize::new(0),
            config,
        })
    }

    /// Get the next worker using round-robin scheduling.
    fn next_worker(&self) -> &WorkerHandle {
        let idx = self.next_worker.fetch_add(1, Ordering::Relaxed) % self.workers.len();
        &self.workers[idx]
    }

    /// Dispatch a request to an available worker and wait for the result.
    pub async fn request(&self, params: RequestParams) -> Result<RecordBatch, BlpAsyncError> {
        let (reply_tx, reply_rx) = oneshot::channel();

        let worker = self.next_worker();
        worker
            .cmd_tx
            .send(WorkerCommand::Request {
                params,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?
            .map_err(BlpAsyncError::BlpError)
    }

    /// Dispatch a streaming request to an available worker.
    ///
    /// Returns a receiver that will receive batches as they arrive.
    pub async fn request_stream(
        &self,
        params: RequestParams,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let (stream_tx, stream_rx) = mpsc::channel(self.config.subscription_stream_capacity);

        let worker = self.next_worker();
        worker
            .cmd_tx
            .send(WorkerCommand::RequestStream {
                params,
                stream: stream_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        Ok(stream_rx)
    }

    /// Get the number of workers in the pool.
    pub fn size(&self) -> usize {
        self.workers.len()
    }

    /// Introspect a service's schema via a worker.
    pub async fn introspect_schema(
        &self,
        service: String,
    ) -> Result<crate::schema::ServiceSchema, BlpAsyncError> {
        let (reply_tx, reply_rx) = oneshot::channel();

        let worker = self.next_worker();
        worker
            .cmd_tx
            .send(WorkerCommand::IntrospectSchema {
                service,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?
            .map_err(BlpAsyncError::BlpError)
    }

    /// Graceful shutdown of all workers.
    pub fn shutdown(&mut self) {
        tracing::info!(pool_size = self.workers.len(), "shutting down request pool");
        for worker in &mut self.workers {
            worker.shutdown();
        }
    }
}

impl Drop for RequestWorkerPool {
    fn drop(&mut self) {
        self.shutdown();
    }
}
