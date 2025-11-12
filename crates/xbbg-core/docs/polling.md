# Polling Events

```rust
use xbbg_core::{SessionOptions, session::Session, EventPoller};

let mut opts = SessionOptions::new()?;
opts.set_default_subscription_service("//blp/mktdata")?;
let session = Session::new(&opts)?;
session.start()?;
session.open_service("//blp/refdata")?;

let poller = EventPoller::new(&session);
loop {
    let event = poller.next(Some(1000))?;
    for msg in event.iter() {
        println!("{}", msg.print_to_string());
    }
}
# Ok::<(), xbbg_core::BlpError>(())
```


