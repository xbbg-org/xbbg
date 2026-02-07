//! Bloomberg service URI constants.
//!
//! Centralizes all service URIs to avoid scattered string literals.

/// Reference data service (bdp, bdh, bds).
pub const REFDATA: &str = "//blp/refdata";

/// Real-time market data service (subscriptions).
pub const MKTDATA: &str = "//blp/mktdata";

/// API field info service (field metadata, validation).
pub const APIFLDS: &str = "//blp/apiflds";
