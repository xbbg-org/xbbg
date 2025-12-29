// Allow large error types - BlpError contains rich context for debugging
#![allow(clippy::result_large_err)]

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

mod correlation;
mod element;
mod errors;
mod event;
#[cfg(feature = "event-log")]
mod event_log;
mod ffi;
mod identity;
mod message;
mod name;
mod options;
mod poller;
mod print;
mod request;
mod request_template;
pub mod requests;
pub mod schema;
mod service;
mod subscription;
mod tag_registry;

pub use correlation::CorrelationId;
pub use element::ElementRef;
pub use errors::{BlpError, CorrelationContext, Result};
pub use event::{Event, EventType};
pub use message::MessageRef;
pub use name::Name;
pub use options::SessionOptions;
pub use poller::EventPoller;
pub use request::Request;
pub use request::RequestBuilder;
pub use request_template::RequestTemplate;
pub use requests::*;
pub use service::Service;
pub use subscription::{SubscriptionList, SubscriptionListBuilder};
pub mod arrow;
pub mod session;

#[cfg(test)]
mod tests;
