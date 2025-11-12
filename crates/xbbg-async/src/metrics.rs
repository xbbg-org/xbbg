use std::sync::atomic::AtomicU64;

#[derive(Default)]
pub struct ShardMetrics {
    pub enqueued: AtomicU64,
    pub dropped: AtomicU64,
    pub routes: AtomicU64,
}

#[derive(Default, Clone, Copy)]
pub struct RouterMetrics {
    pub enqueued: u64,
    pub dropped: u64,
    pub routes: u64,
}


