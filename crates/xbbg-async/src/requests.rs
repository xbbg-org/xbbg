use tokio::sync::{mpsc, oneshot};
use tokio_stream::wrappers::ReceiverStream;
use tokio_stream::Stream;

use xbbg_core::{CorrelationId, Request, Service};

use crate::{AsyncSession, BlpAsyncError};
use xbbg_log::{info, trace};

pub struct RequestHandle {
    _cid: CorrelationId,
    parts_rx: mpsc::Receiver<crate::router::Envelope>,
    final_rx: oneshot::Receiver<crate::router::Envelope>,
}

impl RequestHandle {
    pub(crate) fn new(
        cid: CorrelationId,
        parts_rx: mpsc::Receiver<crate::router::Envelope>,
        final_rx: oneshot::Receiver<crate::router::Envelope>,
    ) -> Self {
        Self {
            _cid: cid,
            parts_rx,
            final_rx,
        }
    }

    pub fn parts(self) -> impl Stream<Item = crate::router::Envelope> {
        ReceiverStream::new(self.parts_rx)
    }

    pub async fn final_(self) -> Result<crate::router::Envelope, BlpAsyncError> {
        trace!("request: awaiting final");
        self.final_rx.await.map_err(|_| BlpAsyncError::Cancelled)
    }
}

impl AsyncSession {
    pub fn send_request(
        &self,
        _service: &Service,
        request: &Request,
        cid: &CorrelationId,
        label: Option<&str>,
    ) -> Result<RequestHandle, BlpAsyncError> {
        // Register route before sending to avoid races
        info!(?cid, label, "request: register route & send");
        let rx = self.router.register_route(cid);
        // Fanout task: split envelopes into parts stream and final oneshot
        let (parts_tx, parts_rx) = mpsc::channel(256);
        let (final_tx, final_rx) = oneshot::channel();
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
        // Send request via core
        self.core
            .send_request(request, None, Some(cid))
            .map_err(|e| BlpAsyncError::Internal(format!("send_request: {e:?}")))?;
        Ok(RequestHandle {
            _cid: cid.clone(),
            parts_rx,
            final_rx,
        })
    }
}
