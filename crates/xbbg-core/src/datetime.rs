//! High-precision datetime type
//!
//! Wrapper around Bloomberg's 16-byte packed datetime structure.
//! Converts to microseconds/nanoseconds since Unix epoch using pure arithmetic.

use crate::ffi;

/// Bloomberg high-precision datetime.
///
/// Wrapper around FFI type with conversion methods.
/// Timestamps are treated as **naive UTC** (offset field is ignored).
///
/// # Examples
///
/// ```ignore
/// // From Bloomberg response
/// let dt = element.get_datetime(0).unwrap();
/// let micros = dt.to_micros();  // Microseconds since Unix epoch
/// let nanos = dt.to_nanos();    // Nanoseconds since Unix epoch
/// ```
///
/// # Size
/// Guaranteed to be 16 bytes (verified at compile time in ffi.rs).
#[repr(transparent)]
#[derive(Copy, Clone, Debug, PartialEq)]
pub struct HighPrecisionDatetime(pub(crate) ffi::blpapi_HighPrecisionDatetime_t);

impl HighPrecisionDatetime {
    /// Create from raw FFI type (for testing/benchmarking).
    ///
    /// # Safety
    /// Caller must ensure the FFI type is properly initialized.
    #[doc(hidden)]
    #[inline(always)]
    pub const fn from_raw(raw: ffi::blpapi_HighPrecisionDatetime_t) -> Self {
        Self(raw)
    }

    /// Access raw FFI type.
    ///
    /// Provides direct access to the underlying Bloomberg datetime structure.
    #[inline(always)]
    pub fn raw(&self) -> &ffi::blpapi_HighPrecisionDatetime_t {
        &self.0
    }

    /// Convert to microseconds since Unix epoch.
    ///
    /// **WARNING**: offset field is IGNORED. Treat result as naive UTC.
    ///
    /// # Performance
    /// Pure arithmetic, no allocations. Target: < 20ns.
    #[inline(always)]
    pub fn to_micros(&self) -> i64 {
        // Read packed fields safely (Rust 2021 handles packed field access via auto-copy)
        let days = days_from_ymd(self.0.year as i32, self.0.month as u32, self.0.day as u32);
        let us = (self.0.hours as i64) * 3_600_000_000
            + (self.0.minutes as i64) * 60_000_000
            + (self.0.seconds as i64) * 1_000_000
            + (self.0.milliseconds as i64) * 1_000
            + (self.0.picoseconds as i64) / 1_000_000;
        days * 86_400_000_000 + us
    }

    /// Convert to nanoseconds since Unix epoch.
    ///
    /// **WARNING**: offset field is IGNORED. Treat result as naive UTC.
    ///
    /// # Performance
    /// Pure arithmetic, no allocations. Target: < 20ns.
    #[inline(always)]
    pub fn to_nanos(&self) -> i64 {
        let days = days_from_ymd(self.0.year as i32, self.0.month as u32, self.0.day as u32);
        let ns = (self.0.hours as i64) * 3_600_000_000_000
            + (self.0.minutes as i64) * 60_000_000_000
            + (self.0.seconds as i64) * 1_000_000_000
            + (self.0.milliseconds as i64) * 1_000_000
            + (self.0.picoseconds as i64) / 1_000;
        days * 86_400_000_000_000 + ns
    }
}

/// Days since Unix epoch. Branchless algorithm (Howard Hinnant).
///
/// This is a well-known civil time algorithm that avoids lookups and branches.
#[inline(always)]
fn days_from_ymd(y: i32, m: u32, d: u32) -> i64 {
    let y = y as i64 - (m <= 2) as i64;
    let era = y.div_euclid(400);
    let yoe = y.rem_euclid(400) as u32;
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe as i64 - 719468
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_datetime(
        year: u16,
        month: u8,
        day: u8,
        hours: u8,
        minutes: u8,
        seconds: u8,
        milliseconds: u16,
    ) -> HighPrecisionDatetime {
        HighPrecisionDatetime(ffi::blpapi_HighPrecisionDatetime_t {
            parts: 0xFF, // all parts present
            hours,
            minutes,
            seconds,
            milliseconds,
            month,
            day,
            year,
            offset: 0,
            picoseconds: 0,
        })
    }

    #[test]
    fn test_datetime_size() {
        // Verify both FFI type and wrapper are 16 bytes
        assert_eq!(
            std::mem::size_of::<ffi::blpapi_HighPrecisionDatetime_t>(),
            16
        );
        assert_eq!(std::mem::size_of::<HighPrecisionDatetime>(), 16);
    }

    #[test]
    fn test_unix_epoch() {
        // 1970-01-01 00:00:00.000 -> 0
        let dt = make_datetime(1970, 1, 1, 0, 0, 0, 0);
        assert_eq!(dt.to_micros(), 0);
    }

    #[test]
    fn test_datetime_conversion() {
        // 2024-06-15 14:30:45.123
        // Using Howard Hinnant's algorithm (well-tested civil time conversion)
        let dt = make_datetime(2024, 6, 15, 14, 30, 45, 123);
        assert_eq!(dt.to_micros(), 1718461845123000);
    }

    #[test]
    fn test_y2k() {
        // 2000-01-01 00:00:00.000 -> 946684800000000
        let dt = make_datetime(2000, 1, 1, 0, 0, 0, 0);
        assert_eq!(dt.to_micros(), 946684800000000);
    }

    #[test]
    fn test_to_nanos() {
        // Verify nanosecond conversion
        let dt = make_datetime(1970, 1, 1, 0, 0, 1, 0);
        assert_eq!(dt.to_nanos(), 1_000_000_000); // 1 second in nanoseconds
    }
}
