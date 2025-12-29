//! Unit tests for xbbg-core.
//!
//! These tests don't require a Bloomberg connection.

use std::sync::Arc;

use crate::correlation::CorrelationId;

// =========================================================================
// Correlation ID tests
// =========================================================================

#[test]
fn test_correlation_id_next_returns_unique_ids() {
    let id1 = CorrelationId::next();
    let id2 = CorrelationId::next();
    let id3 = CorrelationId::next();

    // Each call should return a different ID
    assert_ne!(id1, id2);
    assert_ne!(id2, id3);
    assert_ne!(id1, id3);
}

#[test]
fn test_correlation_id_next_is_sequential() {
    let id1 = CorrelationId::next();
    let id2 = CorrelationId::next();

    if let (CorrelationId::U64(v1), CorrelationId::U64(v2)) = (&id1, &id2) {
        assert_eq!(*v2, *v1 + 1, "IDs should be sequential");
    } else {
        panic!("Expected U64 variants");
    }
}

#[test]
fn test_correlation_id_u64_as_u64() {
    let id = CorrelationId::U64(42);
    assert_eq!(id.as_u64(), Some(42));
    assert_eq!(id.as_tag(), None);
}

#[test]
fn test_correlation_id_tag_as_tag() {
    let id = CorrelationId::Tag(Arc::from("my-request"));
    assert_eq!(id.as_tag(), Some("my-request"));
    assert_eq!(id.as_u64(), None);
}

#[test]
fn test_correlation_id_equality() {
    let id1 = CorrelationId::U64(100);
    let id2 = CorrelationId::U64(100);
    let id3 = CorrelationId::U64(200);

    assert_eq!(id1, id2);
    assert_ne!(id1, id3);

    let tag1 = CorrelationId::Tag(Arc::from("test"));
    let tag2 = CorrelationId::Tag(Arc::from("test"));
    let tag3 = CorrelationId::Tag(Arc::from("other"));

    assert_eq!(tag1, tag2);
    assert_ne!(tag1, tag3);
}

#[test]
fn test_correlation_id_clone() {
    let id = CorrelationId::U64(999);
    let cloned = id.clone();
    assert_eq!(id, cloned);

    let tag = CorrelationId::Tag(Arc::from("cloneable"));
    let cloned_tag = tag.clone();
    assert_eq!(tag, cloned_tag);
}

#[test]
fn test_correlation_id_debug() {
    let id = CorrelationId::U64(123);
    let debug_str = format!("{:?}", id);
    assert!(debug_str.contains("U64"));
    assert!(debug_str.contains("123"));

    let tag = CorrelationId::Tag(Arc::from("debug-test"));
    let debug_str = format!("{:?}", tag);
    assert!(debug_str.contains("Tag"));
    assert!(debug_str.contains("debug-test"));
}
