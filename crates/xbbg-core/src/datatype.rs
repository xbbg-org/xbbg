//! Bloomberg data type enumeration
//!
//! Maps Bloomberg's integer type codes to a Rust enum.

/// Bloomberg field data types.
///
/// Matches Bloomberg's C API integer values exactly via `#[repr(i32)]`.
///
/// # Examples
///
/// ```
/// use xbbg_core::DataType;
///
/// let dt = DataType::from_raw(7);
/// assert_eq!(dt, DataType::Float64);
/// assert!(dt.is_numeric());
/// assert!(!dt.is_complex());
/// ```
#[repr(i32)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash)]
pub enum DataType {
    Bool = 1,
    Char = 2,
    Byte = 3,
    Int32 = 4,
    Int64 = 5,
    Float32 = 6,
    Float64 = 7,
    String = 8,
    ByteArray = 9,
    Date = 10,
    Time = 11,
    Decimal = 12,
    Datetime = 13,
    Enumeration = 14,
    Sequence = 15,
    Choice = 16,
    CorrelationId = 17,
}

impl DataType {
    /// Convert from Bloomberg's raw integer type code.
    ///
    /// Unknown values fall back to `String` for forward compatibility.
    #[inline(always)]
    pub fn from_raw(v: i32) -> Self {
        match v {
            1 => Self::Bool,
            2 => Self::Char,
            3 => Self::Byte,
            4 => Self::Int32,
            5 => Self::Int64,
            6 => Self::Float32,
            7 => Self::Float64,
            8 => Self::String,
            9 => Self::ByteArray,
            10 => Self::Date,
            11 => Self::Time,
            12 => Self::Decimal,
            13 => Self::Datetime,
            14 => Self::Enumeration,
            15 => Self::Sequence,
            16 => Self::Choice,
            17 => Self::CorrelationId,
            _ => Self::String, // Fallback for unknown/future types
        }
    }

    /// Check if this is a numeric type (can be extracted as number).
    ///
    /// Returns `true` for Bool, Char, Byte, Int32, Int64, Float32, Float64, and Decimal.
    #[inline(always)]
    pub fn is_numeric(self) -> bool {
        matches!(
            self,
            Self::Bool
                | Self::Char
                | Self::Byte
                | Self::Int32
                | Self::Int64
                | Self::Float32
                | Self::Float64
                | Self::Decimal
        )
    }

    /// Check if this is a complex/container type.
    ///
    /// Returns `true` for Sequence and Choice types.
    #[inline(always)]
    pub fn is_complex(self) -> bool {
        matches!(self, Self::Sequence | Self::Choice)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_from_raw_known_values() {
        assert_eq!(DataType::from_raw(1), DataType::Bool);
        assert_eq!(DataType::from_raw(4), DataType::Int32);
        assert_eq!(DataType::from_raw(5), DataType::Int64);
        assert_eq!(DataType::from_raw(7), DataType::Float64);
        assert_eq!(DataType::from_raw(8), DataType::String);
        assert_eq!(DataType::from_raw(13), DataType::Datetime);
        assert_eq!(DataType::from_raw(15), DataType::Sequence);
        assert_eq!(DataType::from_raw(17), DataType::CorrelationId);
    }

    #[test]
    fn test_from_raw_unknown_fallback() {
        // Unknown value should fall back to String
        assert_eq!(DataType::from_raw(99), DataType::String);
        assert_eq!(DataType::from_raw(-1), DataType::String);
        assert_eq!(DataType::from_raw(1000), DataType::String);
    }

    #[test]
    fn test_is_numeric() {
        assert!(DataType::Int32.is_numeric());
        assert!(DataType::Int64.is_numeric());
        assert!(DataType::Float32.is_numeric());
        assert!(DataType::Float64.is_numeric());
        assert!(DataType::Bool.is_numeric());
        assert!(DataType::Decimal.is_numeric());

        assert!(!DataType::String.is_numeric());
        assert!(!DataType::Sequence.is_numeric());
        assert!(!DataType::Choice.is_numeric());
    }

    #[test]
    fn test_is_complex() {
        assert!(DataType::Sequence.is_complex());
        assert!(DataType::Choice.is_complex());

        assert!(!DataType::Int32.is_complex());
        assert!(!DataType::String.is_complex());
        assert!(!DataType::Float64.is_complex());
    }
}
