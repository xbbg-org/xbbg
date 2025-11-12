use std::sync::Arc;
use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;
use tokio_stream::Stream;

use xbbg_core::{CorrelationId, SubscriptionList};
use xbbg_core::EventType;

use crate::{BlpAsyncError, Router};
use tracing::{info, trace};

pub struct SubscriptionHandle {
    data_rx: mpsc::Receiver<crate::router::Envelope>,
    status_rx: mpsc::Receiver<crate::router::Envelope>,
    _cids: Vec<CorrelationId>,
    core: Arc<xbbg_core::session::Session>,
}

impl SubscriptionHandle {
    pub fn data(self) -> impl Stream<Item = crate::router::Envelope> {
        ReceiverStream::new(self.data_rx)
    }
    pub fn status(self) -> impl Stream<Item = crate::router::Envelope> {
        ReceiverStream::new(self.status_rx)
    }

    pub fn unsubscribe(&self) -> Result<(), BlpAsyncError> {
        self.core.unsubscribe(&self.as_list_dummy()).map_err(|e| BlpAsyncError::Internal(format!("unsubscribe: {e:?}")))
    }

    fn as_list_dummy(&self) -> SubscriptionList {
        // We don't reconstruct; core requires the original list. Unsubscribe is optional; rely on Drop in many flows.
        // For now, this is a no-op placeholder returning an empty list (won't affect session); users should keep original list if needed.
        SubscriptionList::new().expect("empty list")
    }
}

pub(crate) fn subscribe_with_cids(
    rt: &Arc<tokio::runtime::Runtime>,
    core: Arc<xbbg_core::session::Session>,
    router: Arc<Router>,
    list: &SubscriptionList,
    cids: Vec<CorrelationId>,
    label: Option<&str>,
) -> Result<SubscriptionHandle, BlpAsyncError> {
    // Register routes for each cid
    let mut receivers = Vec::with_capacity(cids.len());
    for cid in &cids {
        trace!(?cid, "subscription: register route");
        receivers.push(router.register_route(cid));
    }
    // Merge receivers into data/status channels
    let (data_tx, data_rx) = mpsc::channel(4096);
    let (status_tx, status_rx) = mpsc::channel(1024);
    for mut rx in receivers {
        let data_tx = data_tx.clone();
        let status_tx = status_tx.clone();
        let _h = rt.spawn(async move {
            while let Some(env) = rx.recv().await {
                match env.event_type {
                    EventType::SubscriptionData => {
                        trace!(msg_type=%env.message_type, "subscription: data");
                        let _ = data_tx.send(env).await;
                    }
                    EventType::SubscriptionStatus => {
                        trace!(msg_type=%env.message_type, "subscription: status");
                        let _ = status_tx.send(env).await;
                    }
                    _ => {
                        // Ignore other event types on this route
                    }
                }
            }
        });
    }
    // Subscribe via core
    info!(count = cids.len(), label, "subscription: subscribe");
    core.subscribe(list, label).map_err(|e| BlpAsyncError::Internal(format!("subscribe: {e:?}")))?;

    Ok(SubscriptionHandle {
        data_rx,
        status_rx,
        _cids: cids,
        core,
    })
}


