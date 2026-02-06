use ahash::AHashMap;
use std::sync::Mutex;
use tokio::sync::mpsc;

use super::Envelope;
use crate::config::AsyncOptions;
use crate::metrics::ShardMetrics;
use xbbg_log::{trace, warn};

pub struct Shard {
    inner: Mutex<AHashMap<u64, Vec<mpsc::Sender<Envelope>>>>,
    queue_size: usize,
    pub metrics: ShardMetrics,
}

impl Shard {
    pub fn new(opts: &AsyncOptions) -> Self {
        Self {
            inner: Mutex::new(AHashMap::new()),
            queue_size: opts.request_queue.max(64),
            metrics: ShardMetrics::default(),
        }
    }

    pub fn register(&self, key: u64) -> mpsc::Receiver<Envelope> {
        let mut map = self.inner.lock().unwrap();
        let (tx, rx) = mpsc::channel(self.queue_size);
        map.entry(key).or_default().push(tx);
        self.metrics
            .routes
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        trace!(key, "router/shard: route registered");
        rx
    }

    pub fn dispatch(&self, key: u64, env: Envelope) {
        let senders = {
            let map = self.inner.lock().unwrap();
            map.get(&key).cloned().unwrap_or_default()
        };
        for tx in senders {
            if tx.try_send(env.clone()).is_ok() {
                self.metrics
                    .enqueued
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            } else {
                self.metrics
                    .dropped
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                warn!(key, msg_type=%env.message_type, event_type=?env.event_type, "router/shard: queue full, dropped");
            }
        }
    }
}
