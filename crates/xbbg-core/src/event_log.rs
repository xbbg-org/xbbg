#![cfg(feature = "event-log")]
use std::collections::VecDeque;
use std::sync::Mutex;

use once_cell::sync::Lazy;

use crate::{Event, EventType, MessageRef};

const MAX_EVENTS: usize = 1024;

pub struct EventRecord {
    pub event_type: EventType,
}

pub static EVENT_LOG: Lazy<Mutex<VecDeque<EventRecord>>> =
    Lazy::new(|| Mutex::new(VecDeque::with_capacity(MAX_EVENTS)));

pub fn record_event(event: &Event) {
    let rec = EventRecord {
        event_type: event.event_type(),
    };
    let mut q = EVENT_LOG.lock().unwrap();
    if q.len() == MAX_EVENTS {
        q.pop_front();
    }
    q.push_back(rec);
}

pub fn dump() -> Vec<EventRecord> {
    let q = EVENT_LOG.lock().unwrap();
    q.iter().cloned().collect()
}
