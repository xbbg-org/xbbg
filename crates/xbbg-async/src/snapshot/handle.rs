use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;
use tokio_stream::Stream;

use xbbg_core::RequestTemplate;

use crate::Envelope;

pub struct SnapshotTemplateHandle {
    pub(crate) tmpl: RequestTemplate,
    status_rx: Option<mpsc::Receiver<Envelope>>,
}

impl SnapshotTemplateHandle {
    pub(crate) fn new(tmpl: RequestTemplate, status_rx: mpsc::Receiver<Envelope>) -> Self {
        Self {
            tmpl,
            status_rx: Some(status_rx),
        }
    }

    pub fn status(&mut self) -> impl Stream<Item = Envelope> {
        let rx = self.status_rx.take().expect("status stream already taken");
        ReceiverStream::new(rx)
    }
}
