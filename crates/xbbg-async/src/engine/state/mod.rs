//! Request and subscription state types with Arrow builders.

mod bulkdata;
mod fieldinfo;
mod generic;
mod histdata;
mod histdata_stream;
mod intradaybar;
mod intradaybar_stream;
mod intradaytick;
mod intradaytick_stream;
pub mod json_schema;
mod raw_json;
mod refdata;
mod subscription;
pub mod typed_builder;

pub use bulkdata::BulkDataState;
pub use fieldinfo::FieldInfoState;
pub use generic::GenericState;
pub use histdata::HistDataState;
pub use histdata_stream::HistDataStreamState;
pub use intradaybar::IntradayBarState;
pub use intradaybar_stream::IntradayBarStreamState;
pub use intradaytick::IntradayTickState;
pub use intradaytick_stream::IntradayTickStreamState;
pub use raw_json::RawJsonState;
pub use refdata::{LongMode, OutputFormat, RefDataState};
pub use subscription::SubscriptionState;

use xbbg_core::{BlpError, MessageRef};

/// Unified request state for Lane B (bulk requests).
pub enum RequestState {
    RefData(RefDataState),
    HistData(HistDataState),
    BulkData(BulkDataState),
    HistDataStream(HistDataStreamState),
    Generic(GenericState),
    RawJson(RawJsonState),
    FieldInfo(FieldInfoState),
}

/// Unified request state for Lane C (intraday requests).
#[allow(clippy::large_enum_variant)]
pub enum IntradayRequestState {
    Bar(IntradayBarState),
    Tick(IntradayTickState),
    BarStream(IntradayBarStreamState),
    TickStream(IntradayTickStreamState),
}

impl RequestState {
    /// Process a PARTIAL_RESPONSE message (append to builders).
    pub fn on_partial(&mut self, msg: &MessageRef) {
        match self {
            RequestState::RefData(s) => s.on_partial(msg),
            RequestState::HistData(s) => s.on_partial(msg),
            RequestState::BulkData(s) => s.on_partial(msg),
            RequestState::HistDataStream(s) => s.on_partial(msg),
            RequestState::Generic(s) => s.on_partial(msg),
            RequestState::RawJson(s) => s.on_partial(msg),
            RequestState::FieldInfo(s) => s.on_partial(msg),
        }
    }

    /// Process the final RESPONSE message, build the result, and send reply.
    pub fn finish_and_reply(self, msg: &MessageRef) {
        match self {
            RequestState::RefData(s) => s.finish(msg),
            RequestState::HistData(s) => s.finish(msg),
            RequestState::BulkData(s) => s.finish(msg),
            RequestState::HistDataStream(s) => s.finish(msg),
            RequestState::Generic(s) => s.finish(msg),
            RequestState::RawJson(s) => s.finish(msg),
            RequestState::FieldInfo(s) => s.finish(msg),
        }
    }

    /// Handle a request failure/error.
    pub fn fail(self, error: BlpError) {
        match self {
            RequestState::RefData(s) => {
                let _ = s.reply.send(Err(error));
            }
            RequestState::HistData(s) => {
                let _ = s.reply.send(Err(error));
            }
            RequestState::BulkData(s) => {
                let _ = s.reply.send(Err(error));
            }
            RequestState::HistDataStream(s) => s.fail(error),
            RequestState::Generic(s) => {
                let _ = s.reply.send(Err(error));
            }
            RequestState::RawJson(s) => {
                let _ = s.reply.send(Err(error));
            }
            RequestState::FieldInfo(s) => {
                let _ = s.reply.send(Err(error));
            }
        }
    }
}

impl IntradayRequestState {
    /// Process a PARTIAL_RESPONSE message (append to builders).
    pub fn on_partial(&mut self, msg: &MessageRef) {
        match self {
            IntradayRequestState::Bar(s) => s.on_partial(msg),
            IntradayRequestState::Tick(s) => s.on_partial(msg),
            IntradayRequestState::BarStream(s) => s.on_partial(msg),
            IntradayRequestState::TickStream(s) => s.on_partial(msg),
        }
    }

    /// Process the final RESPONSE message, build the result, and send reply.
    pub fn finish_and_reply(self, msg: &MessageRef) {
        match self {
            IntradayRequestState::Bar(s) => s.finish(msg),
            IntradayRequestState::Tick(s) => s.finish(msg),
            IntradayRequestState::BarStream(s) => s.finish(msg),
            IntradayRequestState::TickStream(s) => s.finish(msg),
        }
    }

    /// Handle a request failure/error.
    pub fn fail(self, error: BlpError) {
        match self {
            IntradayRequestState::Bar(s) => {
                let _ = s.reply.send(Err(error));
            }
            IntradayRequestState::Tick(s) => {
                let _ = s.reply.send(Err(error));
            }
            IntradayRequestState::BarStream(s) => s.fail(error),
            IntradayRequestState::TickStream(s) => s.fail(error),
        }
    }
}
