// Allow large error types - BlpError contains rich context for debugging
#![allow(clippy::result_large_err)]

mod config;
mod dispatcher;
mod errors;
pub mod field_cache;
mod requests;
mod router;
pub mod schema_cache;
pub mod schema_validation;
mod subscriptions;
mod snapshot {
    pub mod handle;
    pub mod manager;
}
pub mod engine;
mod metrics;
mod status;

use std::sync::Arc;

use tracing::info;
use xbbg_core::session::Session;
use xbbg_core::{CorrelationId, Service, SubscriptionList};

pub use config::{AsyncOptions, BackpressurePolicy};
pub use errors::BlpAsyncError;
pub use metrics::RouterMetrics;
pub use router::{Envelope, Router};
pub use snapshot::handle::SnapshotTemplateHandle;
pub use snapshot::manager::SnapshotTemplateManager;
pub use subscriptions::SubscriptionHandle;

// New worker pool Engine
pub use engine::{Engine, EngineConfig, SlabKey, ValidationMode};

pub struct AsyncSession {
    core: Arc<Session>,
    _pump: std::thread::JoinHandle<()>,
    router: Arc<Router>,
    rt: Arc<tokio::runtime::Runtime>,
}

impl AsyncSession {
    pub fn connect(
        options: xbbg_core::SessionOptions,
        async_opts: AsyncOptions,
    ) -> Result<Self, BlpAsyncError> {
        let rt = Arc::new(
            tokio::runtime::Builder::new_multi_thread()
                .enable_all()
                .build()
                .map_err(|e| BlpAsyncError::Internal(format!("rt build: {e}")))?,
        );
        let sess = Session::new(&options).map_err(|e| BlpAsyncError::Internal(e.to_string()))?;
        sess.start()
            .map_err(|_| BlpAsyncError::Internal("session start failed".into()))?;
        let core = Arc::new(sess);
        let router = Arc::new(Router::new(&async_opts));
        let core_clone = Arc::clone(&core);
        let router_clone = Arc::clone(&router);
        let jh = std::thread::spawn(move || dispatcher::run_pump(core_clone, router_clone));
        info!("AsyncSession connected; pump started");
        Ok(Self {
            core,
            _pump: jh,
            router,
            rt,
        })
    }

    pub fn open_service(&self, name: &str) -> Result<Service, BlpAsyncError> {
        info!(service = name, "open_service");
        self.core
            .open_service(name)
            .map_err(|e| BlpAsyncError::Internal(format!("open_service: {e:?}")))?;
        self.core
            .get_service(name)
            .map_err(|e| BlpAsyncError::Internal(format!("get_service: {e:?}")))
    }

    /// Temporary internal API: subscribe to raw envelopes for a correlation id.
    pub fn subscribe_envelopes(
        &self,
        cid: &CorrelationId,
    ) -> tokio::sync::mpsc::Receiver<Envelope> {
        self.router.register_route(cid)
    }

    pub fn subscribe_with_cids(
        &self,
        list: &SubscriptionList,
        cids: Vec<CorrelationId>,
        label: Option<&str>,
    ) -> Result<SubscriptionHandle, BlpAsyncError> {
        subscriptions::subscribe_with_cids(
            &self.rt,
            Arc::clone(&self.core),
            Arc::clone(&self.router),
            list,
            cids,
            label,
        )
    }

    pub fn snapshot_manager(&self) -> SnapshotTemplateManager {
        SnapshotTemplateManager::new(Arc::clone(&self.core), Arc::clone(&self.router), 50)
    }

    pub fn send_snapshot(
        &self,
        handle: &SnapshotTemplateHandle,
        cid: &CorrelationId,
    ) -> Result<crate::requests::RequestHandle, BlpAsyncError> {
        // Register route and forward as a request
        let rx = self.router.register_route(cid);
        let (parts_tx, parts_rx) = tokio::sync::mpsc::channel(256);
        let (final_tx, final_rx) = tokio::sync::oneshot::channel();
        let mut src_rx = rx;
        self.rt.spawn(async move {
            while let Some(env) = src_rx.recv().await {
                let _ = parts_tx.send(env.clone()).await;
                if env.event_type == xbbg_core::EventType::Response {
                    let _ = final_tx.send(env);
                    break;
                }
            }
        });
        self.core
            .send_request_template_with_cid(&handle.tmpl, Some(cid))
            .map_err(|e| BlpAsyncError::Internal(format!("send_request_template: {e:?}")))?;
        Ok(crate::requests::RequestHandle::new(
            cid.clone(),
            parts_rx,
            final_rx,
        ))
    }

    pub fn service_status(
        &self,
        service: &Service,
        cid: &CorrelationId,
    ) -> Result<tokio::sync::mpsc::Receiver<Envelope>, BlpAsyncError> {
        crate::status::service_status_stream(&self.core, &self.router, service, cid)
    }

    pub fn router_metrics(&self) -> RouterMetrics {
        self.router.metrics()
    }

    pub fn close(self) {}
}

#[cfg(test)]
mod tests;
