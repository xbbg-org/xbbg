pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

mod errors;
mod ffi;
mod name;
mod correlation;
mod options;
mod event;
mod service;
mod request;
mod identity;
mod request_template;
mod message;
mod subscription;
mod element;
mod poller;
mod print;
#[cfg(feature = "event-log")]
mod event_log;
mod tag_registry;
pub mod schema;

pub use errors::{BlpError, CorrelationContext, Result};
pub use name::Name;
pub use correlation::CorrelationId;
pub use options::SessionOptions;
pub use event::{Event, EventType};
pub use service::Service;
pub use request::Request;
pub use request::RequestBuilder;
pub use request_template::RequestTemplate;
pub use message::MessageRef;
pub use element::{ElementRef};
pub use subscription::{SubscriptionList, SubscriptionListBuilder};
pub use poller::EventPoller;
pub mod session;

