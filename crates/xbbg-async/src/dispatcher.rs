use std::sync::Arc;
use xbbg_core::session::Session;

use crate::router::{Envelope, Router};
use std::time::Duration;
use tracing::{debug, info, trace, warn};

pub fn run_pump(session: Arc<Session>, router: Arc<Router>) {
    info!("dispatcher: pump thread started");
    loop {
        match session.next_event(Some(100)) {
            Ok(ev) => {
                let et = ev.event_type();
                trace!(event_type = ?et, "pump: next_event");
                let mut msg_count = 0usize;
                for msg in ev.iter() {
                    // Build a lightweight envelope
                    let ty = msg.message_type();
                    let message_type = ty.as_str().to_string();
                    let request_id = msg.get_request_id().map(|s| s.to_string());
                    let recap_type = msg.recap_type();
                    let text = Some(msg.print_to_string());
                    let envelope = Envelope {
                        message_type,
                        request_id,
                        recap_type: Some(recap_type),
                        event_type: et,
                        text,
                    };
                    // Dispatch to each correlation id (MCM aware)
                    let n = msg.num_correlation_ids();
                    if n == 0 {
                        warn!(
                            "pump: message without correlation ids: type={}",
                            envelope.message_type
                        );
                    }
                    for i in 0..(n as usize) {
                        if let Some(cid) = msg.correlation_id(i) {
                            trace!(cid=?cid, "pump: dispatch");
                            router.dispatch(&cid, envelope.clone());
                        }
                    }
                    msg_count += 1;
                }
                debug!(event_type=?et, messages=msg_count, "pump: event processed");
            }
            Err(_) => {
                // brief backoff on error; basic reconnect friendliness
                debug!("pump: next_event error; backing off");
                std::thread::sleep(Duration::from_millis(50));
            }
        }
    }
}
