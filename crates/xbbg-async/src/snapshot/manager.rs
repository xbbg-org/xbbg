use std::sync::Arc;
use tokio::sync::mpsc;

use xbbg_core::{CorrelationId};

use crate::BlpAsyncError;
use super::handle::SnapshotTemplateHandle;
use tracing::{info, trace};

pub struct SnapshotTemplateManager {
    core: Arc<xbbg_core::session::Session>,
    router: Arc<crate::Router>,
    batch_limit: usize,
}

impl SnapshotTemplateManager {
    pub fn new(core: Arc<xbbg_core::session::Session>, router: Arc<crate::Router>, batch_limit: usize) -> Self {
        Self { core, router, batch_limit }
    }

    pub fn create(&self, subscription: &str, status_cid: &CorrelationId) -> Result<SnapshotTemplateHandle, BlpAsyncError> {
        // Route for status CID
        info!(?status_cid, subscription, "snapshot: create template");
        let rx = self.router.register_route(status_cid);
        let tmpl = self.core.create_snapshot_request_template_with_cid(subscription, Some(status_cid))
            .map_err(|e| BlpAsyncError::Internal(format!("create_snapshot_request_template: {e:?}")))?;
        // Forward all envs on this CID into a status channel (1:1 bridge)
        let (tx, status_rx) = mpsc::channel(1024);
        let mut src_rx = rx;
        tokio::spawn(async move {
            while let Some(env) = src_rx.recv().await {
                trace!(msg_type=%env.message_type, "snapshot: status");
                let _ = tx.send(env).await;
            }
        });
        Ok(SnapshotTemplateHandle::new(tmpl, status_rx))
    }

    pub fn create_many(&self, subs: &[String], make_status_cid: impl Fn(&str) -> CorrelationId) -> Result<Vec<SnapshotTemplateHandle>, BlpAsyncError> {
        let mut out = Vec::with_capacity(subs.len());
        for chunk in subs.chunks(self.batch_limit.max(1)) {
            for s in chunk {
                let cid = make_status_cid(s);
                let h = self.create(s, &cid)?;
                out.push(h);
            }
        }
        Ok(out)
    }
}


