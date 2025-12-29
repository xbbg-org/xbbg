//! Unit tests for xbbg-async engine.
//!
//! These tests don't require a Bloomberg connection.

use crate::config::{AsyncOptions, BackpressurePolicy};
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
    assert_eq!(OverflowPolicy::DropOldest, OverflowPolicy::DropOldest);
    assert_eq!(OverflowPolicy::Block, OverflowPolicy::Block);

    assert_ne!(OverflowPolicy::DropNewest, OverflowPolicy::DropOldest);
    assert_ne!(OverflowPolicy::DropNewest, OverflowPolicy::Block);
    assert_ne!(OverflowPolicy::DropOldest, OverflowPolicy::Block);
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
// AsyncOptions configuration tests
// =========================================================================

#[test]
fn test_async_options_default() {
    let opts = AsyncOptions::default();

    assert_eq!(opts.shards, 32);
    assert_eq!(opts.request_queue, 256);
    assert_eq!(opts.subscription_data_queue, 4096);
    assert_eq!(opts.subscription_status_queue, 1024);
    assert_eq!(opts.template_status_queue, 1024);
    assert_eq!(opts.template_batch_limit, 50);
    assert!(matches!(opts.policy_data, BackpressurePolicy::Block));
    assert!(matches!(opts.policy_status, BackpressurePolicy::Block));
}

#[test]
fn test_async_options_clone() {
    let opts = AsyncOptions::default();
    let cloned = opts.clone();

    assert_eq!(opts.shards, cloned.shards);
    assert_eq!(opts.request_queue, cloned.request_queue);
}

// =========================================================================
// Backpressure policy tests
// =========================================================================

#[test]
fn test_backpressure_policy_variants() {
    let block = BackpressurePolicy::Block;
    let drop_oldest = BackpressurePolicy::DropOldest;
    let error = BackpressurePolicy::Error;

    // Test debug output
    assert!(format!("{:?}", block).contains("Block"));
    assert!(format!("{:?}", drop_oldest).contains("DropOldest"));
    assert!(format!("{:?}", error).contains("Error"));
}

#[test]
fn test_backpressure_policy_clone() {
    let policy = BackpressurePolicy::DropOldest;
    let cloned = policy.clone();
    assert!(matches!(cloned, BackpressurePolicy::DropOldest));
}
