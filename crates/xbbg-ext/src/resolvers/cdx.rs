//! CDX (Credit Default Index) ticker resolution utilities.

use crate::error::{ExtError, Result};

/// Parsed CDX ticker information.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CdxInfo {
    /// The index name (e.g., "CDX IG CDSI")
    pub index: String,
    /// Series indicator - either "GEN" or "S{n}" (e.g., "S45")
    pub series: String,
    /// Tenor (e.g., "5Y")
    pub tenor: String,
    /// Asset class (e.g., "Corp")
    pub asset: String,
    /// Whether this is a generic ticker
    pub is_generic: bool,
    /// Series number if specific (None for GEN)
    pub series_num: Option<u32>,
}

/// Parse a CDX ticker into its components.
///
/// # Examples
///
/// ```
/// use xbbg_ext::resolvers::cdx::cdx_series_from_ticker;
///
/// let info = cdx_series_from_ticker("CDX IG CDSI GEN 5Y Corp").unwrap();
/// assert!(info.is_generic);
/// assert_eq!(info.series, "GEN");
/// assert_eq!(info.tenor, "5Y");
///
/// let info2 = cdx_series_from_ticker("CDX IG CDSI S45 5Y Corp").unwrap();
/// assert!(!info2.is_generic);
/// assert_eq!(info2.series_num, Some(45));
/// ```
pub fn cdx_series_from_ticker(ticker: &str) -> Result<CdxInfo> {
    let parts: Vec<&str> = ticker.split_whitespace().collect();

    if parts.len() < 5 {
        return Err(ExtError::InvalidTicker(ticker.to_string()));
    }

    // Find the position of GEN or S{n}
    let mut series_idx = None;
    let mut series = String::new();
    let mut is_generic = false;
    let mut series_num = None;

    for (i, part) in parts.iter().enumerate() {
        if *part == "GEN" {
            series_idx = Some(i);
            series = "GEN".to_string();
            is_generic = true;
            break;
        } else if part.starts_with('S') && part.len() > 1 {
            let num_part = &part[1..];
            if let Ok(n) = num_part.parse::<u32>() {
                series_idx = Some(i);
                series = part.to_string();
                series_num = Some(n);
                break;
            }
        }
    }

    let series_idx = series_idx.ok_or_else(|| ExtError::InvalidTicker(ticker.to_string()))?;

    // Index is everything before series
    let index = parts[..series_idx].join(" ");

    // Tenor is right after series
    let tenor = if series_idx + 1 < parts.len() {
        parts[series_idx + 1].to_string()
    } else {
        return Err(ExtError::InvalidTicker(ticker.to_string()));
    };

    // Asset is last part
    let asset = parts
        .last()
        .ok_or_else(|| ExtError::InvalidTicker(ticker.to_string()))?
        .to_string();

    Ok(CdxInfo {
        index,
        series,
        tenor,
        asset,
        is_generic,
        series_num,
    })
}

/// Build a CDX ticker from components.
///
/// # Examples
///
/// ```
/// use xbbg_ext::resolvers::cdx::{build_cdx_ticker, CdxInfo};
///
/// let info = CdxInfo {
///     index: "CDX IG CDSI".to_string(),
///     series: "S45".to_string(),
///     tenor: "5Y".to_string(),
///     asset: "Corp".to_string(),
///     is_generic: false,
///     series_num: Some(45),
/// };
///
/// assert_eq!(build_cdx_ticker(&info), "CDX IG CDSI S45 5Y Corp");
/// ```
pub fn build_cdx_ticker(info: &CdxInfo) -> String {
    format!(
        "{} {} {} {}",
        info.index, info.series, info.tenor, info.asset
    )
}

/// Get the previous series ticker for a CDX index.
///
/// # Examples
///
/// ```
/// use xbbg_ext::resolvers::cdx::previous_series_ticker;
///
/// let prev = previous_series_ticker("CDX IG CDSI S45 5Y Corp").unwrap();
/// assert!(prev.is_some());
/// assert!(prev.unwrap().contains("S44"));
///
/// // GEN doesn't have a previous series
/// let prev_gen = previous_series_ticker("CDX IG CDSI GEN 5Y Corp").unwrap();
/// assert!(prev_gen.is_none());
/// ```
pub fn previous_series_ticker(ticker: &str) -> Result<Option<String>> {
    let info = cdx_series_from_ticker(ticker)?;

    if info.is_generic {
        return Ok(None);
    }

    match info.series_num {
        Some(n) if n > 1 => {
            let mut new_info = info.clone();
            new_info.series = format!("S{}", n - 1);
            new_info.series_num = Some(n - 1);
            Ok(Some(build_cdx_ticker(&new_info)))
        }
        _ => Ok(None),
    }
}

/// Convert a generic CDX ticker to a specific series.
///
/// # Examples
///
/// ```
/// use xbbg_ext::resolvers::cdx::gen_to_specific;
///
/// let specific = gen_to_specific("CDX IG CDSI GEN 5Y Corp", 45).unwrap();
/// assert!(specific.contains("S45"));
/// assert!(!specific.contains("GEN"));
/// ```
pub fn gen_to_specific(gen_ticker: &str, series: u32) -> Result<String> {
    let mut info = cdx_series_from_ticker(gen_ticker)?;

    info.series = format!("S{}", series);
    info.series_num = Some(series);
    info.is_generic = false;

    Ok(build_cdx_ticker(&info))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_generic_cdx() {
        let info = cdx_series_from_ticker("CDX IG CDSI GEN 5Y Corp").unwrap();
        assert_eq!(info.index, "CDX IG CDSI");
        assert_eq!(info.series, "GEN");
        assert_eq!(info.tenor, "5Y");
        assert_eq!(info.asset, "Corp");
        assert!(info.is_generic);
        assert_eq!(info.series_num, None);
    }

    #[test]
    fn test_parse_specific_cdx() {
        let info = cdx_series_from_ticker("CDX IG CDSI S45 5Y Corp").unwrap();
        assert_eq!(info.index, "CDX IG CDSI");
        assert_eq!(info.series, "S45");
        assert_eq!(info.tenor, "5Y");
        assert!(!info.is_generic);
        assert_eq!(info.series_num, Some(45));
    }

    #[test]
    fn test_build_cdx_ticker() {
        let info = CdxInfo {
            index: "CDX IG CDSI".to_string(),
            series: "S45".to_string(),
            tenor: "5Y".to_string(),
            asset: "Corp".to_string(),
            is_generic: false,
            series_num: Some(45),
        };
        assert_eq!(build_cdx_ticker(&info), "CDX IG CDSI S45 5Y Corp");
    }

    #[test]
    fn test_previous_series() {
        let prev = previous_series_ticker("CDX IG CDSI S45 5Y Corp")
            .unwrap()
            .unwrap();
        assert!(prev.contains("S44"));

        // S1 has no previous
        let prev_s1 = previous_series_ticker("CDX IG CDSI S1 5Y Corp").unwrap();
        assert!(prev_s1.is_none());

        // GEN has no previous
        let prev_gen = previous_series_ticker("CDX IG CDSI GEN 5Y Corp").unwrap();
        assert!(prev_gen.is_none());
    }

    #[test]
    fn test_gen_to_specific() {
        let specific = gen_to_specific("CDX IG CDSI GEN 5Y Corp", 45).unwrap();
        assert_eq!(specific, "CDX IG CDSI S45 5Y Corp");
    }

    #[test]
    fn test_invalid_ticker() {
        assert!(cdx_series_from_ticker("INVALID").is_err());
        assert!(cdx_series_from_ticker("CDX IG").is_err());
    }
}
