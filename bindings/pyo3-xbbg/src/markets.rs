use std::collections::HashMap;

use pyo3::prelude::*;
use xbbg_ext::markets::sessions;

/// A plain-data representation of [`sessions::MarketRule`] that pyo3 can
/// convert to a Python dict automatically — no GIL-bound PyObject needed.
#[derive(Clone, Debug, IntoPyObject)]
struct MarketRuleDict {
    pre_minutes: i32,
    post_minutes: i32,
    lunch_start_min: Option<i32>,
    lunch_end_min: Option<i32>,
    is_continuous: bool,
}

/// Derive session windows from regular trading hours.
///
/// Returns dict with keys: day, allday, pre, post, am, pm.
/// Each value is a ``(start, end)`` tuple of ``"HH:MM"`` strings.
/// Keys are omitted when the session does not apply.
#[pyfunction]
fn ext_derive_sessions(
    day_start: &str,
    day_end: &str,
    mic: Option<&str>,
    exch_code: Option<&str>,
) -> HashMap<String, (String, String)> {
    let sw = sessions::derive_sessions(day_start, day_end, mic, exch_code);
    let mut result = HashMap::new();
    if let Some(v) = sw.day {
        result.insert("day".to_string(), v);
    }
    if let Some(v) = sw.allday {
        result.insert("allday".to_string(), v);
    }
    if let Some(v) = sw.pre {
        result.insert("pre".to_string(), v);
    }
    if let Some(v) = sw.post {
        result.insert("post".to_string(), v);
    }
    if let Some(v) = sw.am {
        result.insert("am".to_string(), v);
    }
    if let Some(v) = sw.pm {
        result.insert("pm".to_string(), v);
    }
    result
}

/// Look up market rule by MIC code or Bloomberg exchange code.
///
/// Returns dict with rule fields, or ``None`` if no rule matches.
#[pyfunction]
fn ext_get_market_rule(mic: Option<&str>, exch_code: Option<&str>) -> Option<MarketRuleDict> {
    let rule = sessions::get_market_rule(mic, exch_code)?;
    Some(MarketRuleDict {
        pre_minutes: rule.pre_minutes,
        post_minutes: rule.post_minutes,
        lunch_start_min: rule.lunch_start_min,
        lunch_end_min: rule.lunch_end_min,
        is_continuous: rule.is_continuous,
    })
}

/// Infer timezone from country ISO code.
#[pyfunction]
fn ext_infer_timezone(country_iso: &str) -> Option<String> {
    sessions::infer_timezone_from_country(country_iso).map(String::from)
}

/// Register all markets functions on the module.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ext_derive_sessions, m)?)?;
    m.add_function(wrap_pyfunction!(ext_get_market_rule, m)?)?;
    m.add_function(wrap_pyfunction!(ext_infer_timezone, m)?)?;
    Ok(())
}
