use tokio::sync::mpsc;

use xbbg_core::{CorrelationId, Service};

use crate::{BlpAsyncError, Envelope, Router};
use tracing::info;

pub fn service_status_stream(
    core: &xbbg_core::session::Session,
    router: &Router,
    service: &Service,
    cid: &CorrelationId,
) -> Result<mpsc::Receiver<Envelope>, BlpAsyncError> {
    core.set_status_correlation_id(service, cid)
        .map_err(|e| BlpAsyncError::Internal(format!("set_status_correlation_id: {e:?}")))?;
    info!(?cid, "status: registered service status cid");
    let rx = router.register_route(cid);
    Ok(rx)
}
