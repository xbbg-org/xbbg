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
use super::{BlpAsyncError, EngineConfig, RequestParams, WorkerHealth};

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

        xbbg_log::info!(pool_size = size, "creating request worker pool");

        let mut workers = Vec::with_capacity(size);
        for id in 0..size {
            let handle = WorkerHandle::spawn(id, config.clone()).map_err(|e| {
                BlpAsyncError::BlpError(BlpError::Internal {
                    detail: format!("failed to spawn worker {}: {}", id, e),
                })
            })?;
            workers.push(handle);
        }

        xbbg_log::info!(pool_size = size, "request worker pool ready");

        Ok(Self {
            workers,
            next_worker: AtomicUsize::new(0),
            config,
        })
    }

    fn next_healthy_worker(&self) -> Result<&WorkerHandle, BlpAsyncError> {
        let len = self.workers.len();
        let start = self.next_worker.fetch_add(1, Ordering::Relaxed) % len;

        for offset in 0..len {
            let idx = (start + offset) % len;
            let worker = &self.workers[idx];
            if worker.health() != WorkerHealth::Dead {
                return Ok(worker);
            }
        }

        Err(BlpAsyncError::AllWorkersDown { pool_size: len })
    }

    fn retry_delay(&self, attempt: usize) -> u64 {
        if attempt == 0 {
            return 0;
        }

        let policy = &self.config.retry_policy;
        let exponent = (attempt - 1) as f64;
        let delay = (policy.initial_delay_ms as f64) * policy.backoff_factor.powf(exponent);
        let bounded = if delay.is_finite() {
            delay.min(policy.max_delay_ms as f64)
        } else {
            policy.max_delay_ms as f64
        };

        bounded.max(0.0).round() as u64
    }

    fn is_retryable(&self, error: &BlpError) -> bool {
        match error {
            BlpError::Internal { detail } => {
                let detail = detail.to_ascii_lowercase();
                detail.contains("session")
                    || detail.contains("connection")
                    || detail.contains("transport")
            }
            _ => false,
        }
    }

    /// Dispatch a request to an available worker and wait for the result.
    pub async fn request(&self, params: RequestParams) -> Result<RecordBatch, BlpAsyncError> {
        let max_attempts = 1 + self.config.retry_policy.max_retries as usize;
        let mut last_error = None;

        for attempt in 0..max_attempts {
            if attempt > 0 {
                let delay = self.retry_delay(attempt);
                tokio::time::sleep(std::time::Duration::from_millis(delay)).await;
                xbbg_log::info!(attempt = attempt, delay_ms = delay, "retrying request");
            }

            let worker = match self.next_healthy_worker() {
                Ok(worker) => worker,
                Err(error) => {
                    last_error = Some(error);
                    continue;
                }
            };

            let (reply_tx, reply_rx) = oneshot::channel();

            xbbg_log::debug!(
                worker_id = worker.id,
                service = %params.service,
                operation = %params.operation,
                attempt = attempt,
                "dispatching request"
            );

            if worker
                .cmd_tx
                .send(WorkerCommand::Request {
                    params: params.clone(),
                    reply: reply_tx,
                })
                .await
                .is_err()
            {
                if attempt + 1 < max_attempts {
                    last_error = Some(BlpAsyncError::ChannelClosed);
                    continue;
                }
                return Err(BlpAsyncError::ChannelClosed);
            }

            match reply_rx.await {
                Ok(Ok(batch)) => return Ok(batch),
                Ok(Err(error)) if self.is_retryable(&error) && attempt + 1 < max_attempts => {
                    last_error = Some(BlpAsyncError::BlpError(error));
                    continue;
                }
                Ok(Err(error)) => return Err(BlpAsyncError::BlpError(error)),
                Err(_) if attempt + 1 < max_attempts => {
                    last_error = Some(BlpAsyncError::ChannelClosed);
                    continue;
                }
                Err(_) => return Err(BlpAsyncError::ChannelClosed),
            }
        }

        Err(last_error.unwrap_or(BlpAsyncError::ChannelClosed))
    }

    /// Dispatch a streaming request to an available worker.
    ///
    /// Returns a receiver that will receive batches as they arrive.
    pub async fn request_stream(
        &self,
        params: RequestParams,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let (stream_tx, stream_rx) = mpsc::channel(self.config.subscription_stream_capacity);

        let worker = self.next_healthy_worker()?;
        xbbg_log::debug!(
            worker_id = worker.id,
            service = %params.service,
            operation = %params.operation,
            "dispatching stream request"
        );
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

    pub fn worker_health(&self) -> Vec<(usize, WorkerHealth)> {
        self.workers
            .iter()
            .map(|worker| (worker.id, worker.health()))
            .collect()
    }

    /// Introspect a service's schema via a worker.
    pub async fn introspect_schema(
        &self,
        service: String,
    ) -> Result<crate::schema::ServiceSchema, BlpAsyncError> {
        let (reply_tx, reply_rx) = oneshot::channel();

        let worker = self.next_healthy_worker()?;
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

    /// Signal shutdown to all workers (non-blocking).
    ///
    /// Workers will terminate when they see the shutdown signal.
    /// Used by Drop to avoid blocking during interpreter shutdown.
    pub fn signal_shutdown(&self) {
        xbbg_log::info!(
            pool_size = self.workers.len(),
            "signaling request pool shutdown"
        );
        for worker in &self.workers {
            worker.signal_shutdown();
        }
    }

    /// Graceful shutdown - waits for all workers to finish (blocking).
    ///
    /// Use this for clean shutdown when you can afford to wait.
    pub fn shutdown_blocking(&mut self) {
        xbbg_log::info!(
            pool_size = self.workers.len(),
            "shutting down request pool (blocking)"
        );
        for worker in &mut self.workers {
            worker.shutdown_blocking();
        }
    }
}

impl Drop for RequestWorkerPool {
    fn drop(&mut self) {
        // Non-blocking: just signal, don't wait
        self.signal_shutdown();
    }
}
