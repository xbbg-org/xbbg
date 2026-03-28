//! Unit tests for xbbg-async engine.
//!
//! These tests don't require a Bloomberg connection.

use crate::engine::{EngineConfig, OutputFormat, OverflowPolicy};

// =========================================================================
// Engine configuration tests
// =========================================================================

#[test]
fn test_engine_config_default_values() {
    let config = EngineConfig::default();

    assert_eq!(config.server_host, "localhost");
    assert_eq!(config.server_port, 8194);
    assert!(config.max_event_queue_size > 0);
    assert!(config.command_queue_size > 0);
    assert!(config.subscription_flush_threshold > 0);
    assert!(config.subscription_stream_capacity > 0);
}

#[test]
fn test_engine_config_custom_values() {
    let config = EngineConfig {
        server_host: "bloomberg.example.com".to_string(),
        server_port: 8195,
        max_event_queue_size: 20000,
        command_queue_size: 512,
        subscription_flush_threshold: 200,
        subscription_stream_capacity: 2048,
        overflow_policy: OverflowPolicy::Block,
        ..Default::default()
    };

    assert_eq!(config.server_host, "bloomberg.example.com");
    assert_eq!(config.server_port, 8195);
    assert_eq!(config.max_event_queue_size, 20000);
    assert_eq!(config.command_queue_size, 512);
    assert_eq!(config.overflow_policy, OverflowPolicy::Block);
}

// =========================================================================
// Overflow policy tests
// =========================================================================

#[test]
fn test_overflow_policy_default() {
    let policy = OverflowPolicy::default();
    assert_eq!(policy, OverflowPolicy::DropNewest);
}

#[test]
fn test_overflow_policy_variants() {
    assert_eq!(OverflowPolicy::DropNewest, OverflowPolicy::DropNewest);
    assert_eq!(OverflowPolicy::Block, OverflowPolicy::Block);

    assert_ne!(OverflowPolicy::DropNewest, OverflowPolicy::Block);
}

#[test]
fn test_overflow_policy_clone() {
    let policy = OverflowPolicy::Block;
    let cloned = policy;
    assert_eq!(policy, cloned);
}

#[test]
fn test_overflow_policy_debug() {
    let policy = OverflowPolicy::DropNewest;
    let debug_str = format!("{:?}", policy);
    assert!(debug_str.contains("DropNewest"));
}

// =========================================================================
// Output format tests
// =========================================================================

#[test]
fn test_output_format_default() {
    let format = OutputFormat::default();
    assert_eq!(format, OutputFormat::Long);
}

#[test]
fn test_output_format_variants() {
    assert_eq!(OutputFormat::Wide, OutputFormat::Wide);
    assert_eq!(OutputFormat::Long, OutputFormat::Long);
    assert_ne!(OutputFormat::Wide, OutputFormat::Long);
}

#[test]
fn test_output_format_clone() {
    let format = OutputFormat::Wide;
    let cloned = format;
    assert_eq!(format, cloned);
}

// =========================================================================
// BlpAsyncError tests
// =========================================================================

use crate::errors::BlpAsyncError;
use xbbg_core::BlpError;

#[test]
fn test_blp_async_error_from_blp_error_session_start() {
    let blp_err = BlpError::SessionStart {
        source: None,
        label: Some("test label".to_string()),
    };

    let async_err: BlpAsyncError = blp_err.into();

    // Should be wrapped in Blp variant
    assert!(matches!(async_err, BlpAsyncError::Blp(_)));

    // Error message should contain the original error info
    let msg = async_err.to_string();
    assert!(
        msg.contains("session start"),
        "Expected 'session start' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_from_blp_error_open_service() {
    let blp_err = BlpError::OpenService {
        service: "//blp/refdata".to_string(),
        source: None,
        label: Some("connection refused".to_string()),
    };

    let async_err: BlpAsyncError = blp_err.into();

    assert!(matches!(async_err, BlpAsyncError::Blp(_)));
    let msg = async_err.to_string();
    assert!(
        msg.contains("open service"),
        "Expected 'open service' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_from_blp_error_request_failure() {
    let blp_err = BlpError::RequestFailure {
        service: "//blp/refdata".to_string(),
        operation: Some("ReferenceDataRequest".to_string()),
        cid: None,
        label: Some("invalid security".to_string()),
        request_id: Some("req-123".to_string()),
        source: None,
    };

    let async_err: BlpAsyncError = blp_err.into();

    assert!(matches!(async_err, BlpAsyncError::Blp(_)));
    let msg = async_err.to_string();
    assert!(
        msg.contains("request failed"),
        "Expected 'request failed' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_from_blp_error_invalid_argument() {
    let blp_err = BlpError::InvalidArgument {
        detail: "securities cannot be empty".to_string(),
    };

    let async_err: BlpAsyncError = blp_err.into();

    assert!(matches!(async_err, BlpAsyncError::Blp(_)));
    let msg = async_err.to_string();
    assert!(
        msg.contains("invalid argument"),
        "Expected 'invalid argument' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_from_blp_error_timeout() {
    let blp_err = BlpError::Timeout;

    let async_err: BlpAsyncError = blp_err.into();

    assert!(matches!(async_err, BlpAsyncError::Blp(_)));
    let msg = async_err.to_string();
    assert!(
        msg.contains("timed out"),
        "Expected 'timed out' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_from_blp_error_internal() {
    let blp_err = BlpError::Internal {
        detail: "unexpected state".to_string(),
    };

    let async_err: BlpAsyncError = blp_err.into();

    assert!(matches!(async_err, BlpAsyncError::Blp(_)));
    let msg = async_err.to_string();
    assert!(
        msg.contains("internal error"),
        "Expected 'internal error' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_internal_variant() {
    let async_err = BlpAsyncError::Internal("engine shutdown".to_string());

    let msg = async_err.to_string();
    assert!(
        msg.contains("engine shutdown"),
        "Expected 'engine shutdown' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_stream_full() {
    let async_err = BlpAsyncError::StreamFull;

    let msg = async_err.to_string();
    assert!(
        msg.contains("stream full"),
        "Expected 'stream full' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_cancelled() {
    let async_err = BlpAsyncError::Cancelled;

    let msg = async_err.to_string();
    assert!(
        msg.contains("cancelled"),
        "Expected 'cancelled' in: {}",
        msg
    );
}

#[test]
fn test_blp_async_error_timeout_variant() {
    let async_err = BlpAsyncError::Timeout;

    let msg = async_err.to_string();
    assert!(msg.contains("timeout"), "Expected 'timeout' in: {}", msg);
}

#[test]
fn test_blp_async_error_blp_preserves_context() {
    // Test that wrapping BlpError preserves all structured context
    let blp_err = BlpError::RequestFailure {
        service: "//blp/refdata".to_string(),
        operation: Some("HistoricalDataRequest".to_string()),
        cid: None,
        label: Some("field not found: INVALID_FIELD".to_string()),
        request_id: Some("correlation-456".to_string()),
        source: None,
    };

    let async_err = BlpAsyncError::Blp(blp_err);

    // Extract the inner BlpError to verify context is preserved
    if let BlpAsyncError::Blp(inner) = async_err {
        if let BlpError::RequestFailure {
            service,
            operation,
            label,
            request_id,
            ..
        } = inner
        {
            assert_eq!(service, "//blp/refdata");
            assert_eq!(operation, Some("HistoricalDataRequest".to_string()));
            assert_eq!(label, Some("field not found: INVALID_FIELD".to_string()));
            assert_eq!(request_id, Some("correlation-456".to_string()));
        } else {
            panic!("Expected RequestFailure variant");
        }
    } else {
        panic!("Expected Blp variant");
    }
}

#[test]
fn test_blp_async_error_is_send_sync() {
    // BlpAsyncError must be Send + Sync for use across async boundaries
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<BlpAsyncError>();
}
