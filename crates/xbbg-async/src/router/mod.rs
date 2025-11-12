mod shard;

use ahash::AHasher;
use std::hash::{Hash, Hasher};

use tokio::sync::mpsc;

use xbbg_core::CorrelationId;

use crate::config::AsyncOptions;
use shard::Shard;
use crate::metrics::{RouterMetrics};
use tracing::trace;

#[derive(Clone, Debug)]
pub struct Envelope {
    pub message_type: String,
    pub request_id: Option<String>,
    pub recap_type: Option<i32>,
    pub event_type: xbbg_core::EventType,
    pub text: Option<String>,
}

pub struct Router {
    shards: Vec<Shard>,
    _opts: AsyncOptions,
}

impl Router {
    pub fn new(opts: &AsyncOptions) -> Self {
        let shards = (0..opts.shards).map(|_| Shard::new(opts)).collect();
        Self { shards, _opts: opts.clone() }
    }

    fn shard_for(&self, key: u64) -> &Shard {
        let idx = (key as usize) % self.shards.len();
        &self.shards[idx]
    }

    fn key_for_cid(cid: &CorrelationId) -> u64 {
        match cid {
            CorrelationId::U64(v) => *v,
            CorrelationId::Tag(s) => {
                let mut h = AHasher::default();
                "tag".hash(&mut h);
                s.as_ref().hash(&mut h);
                h.finish()
            }
        }
    }

    pub fn register_route(&self, cid: &CorrelationId) -> mpsc::Receiver<Envelope> {
        let key = Self::key_for_cid(cid);
        trace!(?cid, key, "router: register_route");
        self.shard_for(key).register(key)
    }

    pub fn dispatch(&self, cid: &CorrelationId, env: Envelope) {
        let key = Self::key_for_cid(cid);
        trace!(?cid, key, msg_type=%env.message_type, event_type=?env.event_type, "router: dispatch");
        self.shard_for(key).dispatch(key, env);
    }

    pub fn metrics(&self) -> RouterMetrics {
        let mut m = RouterMetrics::default();
        for s in &self.shards {
            m.enqueued += s.metrics.enqueued.load(std::sync::atomic::Ordering::Relaxed);
            m.dropped += s.metrics.dropped.load(std::sync::atomic::Ordering::Relaxed);
            m.routes += s.metrics.routes.load(std::sync::atomic::Ordering::Relaxed);
        }
        m
    }
}


