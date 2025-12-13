#[derive(Clone, Debug)]
pub enum BackpressurePolicy {
    Block,
    DropOldest,
    Error,
}

#[derive(Clone, Debug)]
pub struct AsyncOptions {
    pub shards: usize,
    pub request_queue: usize,
    pub subscription_data_queue: usize,
    pub subscription_status_queue: usize,
    pub template_status_queue: usize,
    pub policy_data: BackpressurePolicy,
    pub policy_status: BackpressurePolicy,
    pub template_batch_limit: usize,
}

impl Default for AsyncOptions {
    fn default() -> Self {
        Self {
            shards: 32,
            request_queue: 256,
            subscription_data_queue: 4096,
            subscription_status_queue: 1024,
            template_status_queue: 1024,
            policy_data: BackpressurePolicy::Block,
            policy_status: BackpressurePolicy::Block,
            template_batch_limit: 50,
        }
    }
}
