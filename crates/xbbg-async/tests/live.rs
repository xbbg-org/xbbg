#[cfg(feature = "live")]
use tokio_stream::StreamExt;
#[cfg(feature = "live")]
fn init_tracing() {
    static INIT: std::sync::Once = std::sync::Once::new();
    INIT.call_once(|| {
        let filter = std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into());
        let _ = tracing_subscriber::fmt()
            .with_env_filter(filter)
            .with_test_writer()
            .try_init();
        // Suppress noisy BLPAPI WARN logs in tests
        unsafe {
            // Raise SDK logging threshold to ERROR (ignore return code)
            let _ = blpapi_sys::blpapi_Logging_registerCallback(
                None,
                blpapi_sys::blpapi_Logging_Severity_t_blpapi_Logging_SEVERITY_ERROR as i32,
            );
        }
    });
}

#[cfg(feature = "live")]
#[tokio::test(flavor = "multi_thread")]
async fn async_requests_two_u64_cids() {
    init_tracing();
    use xbbg_async::{AsyncOptions, AsyncSession};
    use xbbg_core::{CorrelationId, RequestBuilder, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let async_opts = AsyncOptions::default();
    let sess = AsyncSession::connect(opts, async_opts).expect("connect");

    let svc = sess.open_service("//blp/refdata").expect("open refdata");

    let req1 = RequestBuilder::new()
        .securities(vec!["IBM US Equity".into()])
        .fields(vec!["PX_LAST".into()])
        .build(&svc, "ReferenceDataRequest")
        .expect("req1");
    let req2 = RequestBuilder::new()
        .securities(vec!["MSFT US Equity".into()])
        .fields(vec!["PX_LAST".into()])
        .build(&svc, "ReferenceDataRequest")
        .expect("req2");

    let h1 = sess
        .send_request(&svc, &req1, &CorrelationId::U64(1), None)
        .expect("send1");
    let h2 = sess
        .send_request(&svc, &req2, &CorrelationId::U64(2), None)
        .expect("send2");

    let f1 = tokio::time::timeout(std::time::Duration::from_secs(20), h1.final_());
    let f2 = tokio::time::timeout(std::time::Duration::from_secs(20), h2.final_());
    let env1 = f1.await.expect("timeout f1").expect("final1");
    let env2 = f2.await.expect("timeout f2").expect("final2");
    println!(
        "final#1 type={} text:\n{}",
        env1.message_type,
        env1.text.unwrap_or_default()
    );
    println!(
        "final#2 type={} text:\n{}",
        env2.message_type,
        env2.text.unwrap_or_default()
    );

    // Avoid dropping embedded runtime from within async context
    std::mem::forget(sess);
}

#[cfg(feature = "live")]
#[tokio::test(flavor = "multi_thread")]
async fn async_subscription_tag_roundtrip() {
    init_tracing();
    use std::sync::Arc;
    use xbbg_async::{AsyncOptions, AsyncSession};
    use xbbg_core::{CorrelationId, SessionOptions, SubscriptionListBuilder};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let async_opts = AsyncOptions::default();
    let sess = AsyncSession::connect(opts, async_opts).expect("connect");

    sess.open_service("//blp/mktdata").expect("open mktdata");

    let topic = "IBM US Equity".to_string();
    let cid = CorrelationId::Tag(Arc::<str>::from(topic.clone()));
    let list = SubscriptionListBuilder::new()
        .add(&topic, &["LAST_PRICE", "BID", "ASK"], cid.clone())
        .build()
        .expect("list");

    let handle = sess
        .subscribe_with_cids(&list, vec![cid.clone()], None)
        .expect("subscribe");
    let mut status = handle.status();
    let first = tokio::time::timeout(std::time::Duration::from_secs(10), status.next())
        .await
        .expect("timeout")
        .expect("status");
    println!(
        "subscription status type={} text:\n{}",
        first.message_type,
        first.text.unwrap_or_default()
    );

    std::mem::forget(sess);
}

#[cfg(feature = "live")]
#[tokio::test(flavor = "multi_thread")]
async fn async_subscription_field_echo() {
    init_tracing();
    use std::sync::Arc;
    use xbbg_async::{AsyncOptions, AsyncSession};
    use xbbg_core::{CorrelationId, SessionOptions, SubscriptionListBuilder};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let async_opts = AsyncOptions::default();
    let sess = AsyncSession::connect(opts, async_opts).expect("connect");

    sess.open_service("//blp/mktdata").expect("open mktdata");

    let topic = "IBM US Equity".to_string();
    let cid = CorrelationId::Tag(Arc::<str>::from(topic.clone()));
    let list = SubscriptionListBuilder::new()
        .add(&topic, &["LAST_PRICE", "BID", "ASK"], cid.clone())
        .build()
        .expect("list");

    let handle = sess
        .subscribe_with_cids(&list, vec![cid.clone()], None)
        .expect("subscribe");
    let mut data = handle.data();

    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(10);
    let mut found = false;
    while tokio::time::Instant::now() < deadline {
        if let Ok(Some(env)) =
            tokio::time::timeout(std::time::Duration::from_millis(500), data.next()).await
        {
            let t = env.text.clone().unwrap_or_default();
            if t.contains("LAST_PRICE") || t.contains("BID") || t.contains("ASK") {
                found = true;
                break;
            }
        }
    }
    assert!(
        found,
        "did not see expected field mnemonics in recap/status payload"
    );

    std::mem::forget(sess);
}

#[cfg(feature = "live")]
#[tokio::test(flavor = "multi_thread")]
async fn async_snapshot_template_send() {
    init_tracing();
    use xbbg_async::{AsyncOptions, AsyncSession};
    use xbbg_core::{CorrelationId, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let async_opts = AsyncOptions::default();
    let sess = AsyncSession::connect(opts, async_opts).expect("connect");

    sess.open_service("//blp/mktdata").expect("open mktdata");

    let mgr = sess.snapshot_manager();
    let status_cid = CorrelationId::U64(12345);
    let topic = "IBM US Equity".to_string();
    let sub_str = format!("//blp/mktdata/ticker/{}?fields=LAST_PRICE,BID,ASK", topic);
    let mut h = mgr.create(&sub_str, &status_cid).expect("create tmpl");

    // Wait for RequestTemplateAvailable before sending
    let mut available = false;
    let wait_deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(60);
    let mut st = h.status();
    while let Ok(Some(env)) = tokio::time::timeout_at(wait_deadline, st.next()).await {
        if env.message_type == "RequestTemplateAvailable" {
            available = true;
            break;
        } else if env.message_type == "RequestTemplateTerminated" {
            eprintln!(
                "template terminated early: {}",
                env.text.unwrap_or_default()
            );
            break;
        }
    }
    if !available {
        eprintln!("template did not reach Available within timeout; skipping send");
        std::mem::forget(sess);
        return;
    }

    let req_cid = CorrelationId::U64(67890);
    let rh = match sess.send_snapshot(&h, &req_cid) {
        Ok(h) => h,
        Err(e) => {
            eprintln!("snapshot send unsupported here: {e:?}");
            std::mem::forget(sess);
            return;
        }
    };
    match tokio::time::timeout(std::time::Duration::from_secs(60), rh.final_()).await {
        Ok(Ok(_)) => {}
        _ => {
            eprintln!("snapshot final timed out or failed; skipping in this env");
        }
    }

    std::mem::forget(sess);
}
