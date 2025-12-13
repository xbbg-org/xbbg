use crate::errors::Result;
use crate::event::Event;
use crate::session::Session;

pub struct EventPoller<'a> {
    session: &'a Session,
}

impl<'a> EventPoller<'a> {
    pub fn new(session: &'a Session) -> Self {
        Self { session }
    }

    pub fn next(&self, timeout_ms: Option<u32>) -> Result<Event> {
        self.session.next_event(timeout_ms)
    }
}
