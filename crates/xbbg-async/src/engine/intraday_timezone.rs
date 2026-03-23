//! Intraday bar/tick timezone handling (request wall-clock → UTC, output UTC → display TZ).
//!
//! Bloomberg `startDateTime` / `endDateTime` are sent as UTC instants; tick/bar `time` is
//! returned as Arrow `timestamp[us, tz=UTC]`. Callers pass `request_tz` / `output_tz` on
//! [`crate::engine::RequestParams`] to interpret naive inputs and relabel output timestamps.

use std::str::FromStr;

use arrow::array::{Array, TimestampMicrosecondArray};
use arrow::datatypes::Field;
use arrow::datatypes::{DataType, TimeUnit};
use arrow::error::ArrowError;
use arrow::record_batch::RecordBatch;
use chrono::{DateTime, NaiveDate, NaiveDateTime, TimeZone, Utc};
use chrono_tz::Tz;
use tokio::sync::mpsc;
use xbbg_core::BlpError;

use crate::errors::BlpAsyncError;
use crate::services::Operation;

use super::Engine;
use super::RequestParams;

/// Resolve `UTC` | `local` | `exchange` | `NY`/`LN`/… | IANA into an IANA timezone name.
pub(crate) async fn resolve_tz_label(
    engine: &Engine,
    label: &str,
    security: Option<&str>,
) -> Result<String, BlpAsyncError> {
    let s = label.trim();
    if s.is_empty() || s.eq_ignore_ascii_case("utc") {
        return Ok("UTC".to_string());
    }
    if s.eq_ignore_ascii_case("local") {
        return Ok(local_iana_timezone());
    }
    if s.eq_ignore_ascii_case("exchange") {
        let sec = security.ok_or_else(|| BlpAsyncError::ConfigError {
            detail: "output_tz/request_tz='exchange' requires a security on the request"
                .to_string(),
        })?;
        let info = engine.resolve_exchange(sec).await;
        if info.timezone.is_empty() {
            return Err(BlpAsyncError::ConfigError {
                detail: format!("could not resolve exchange timezone for {sec}"),
            });
        }
        return Ok(info.timezone);
    }
    if let Some(iana) = alias_timezone(s) {
        return Ok(iana.to_string());
    }
    if s.contains(' ') {
        let info = engine.resolve_exchange(s).await;
        if !info.timezone.is_empty() {
            return Ok(info.timezone);
        }
    }
    // Validate IANA
    let _: Tz = s.parse().map_err(|_| BlpAsyncError::ConfigError {
        detail: format!("unknown timezone label: {label}"),
    })?;
    Ok(s.to_string())
}

fn alias_timezone(label: &str) -> Option<&'static str> {
    match label.to_uppercase().as_str() {
        "NY" => Some("America/New_York"),
        "LN" => Some("Europe/London"),
        "TK" => Some("Asia/Tokyo"),
        "HK" => Some("Asia/Hong_Kong"),
        _ => None,
    }
}

fn local_iana_timezone() -> String {
    iana_time_zone::get_timezone().unwrap_or_else(|_| "UTC".to_string())
}

fn intraday_operation(params: &RequestParams) -> bool {
    matches!(
        Operation::from_str(params.operation.as_str()),
        Ok(Operation::IntradayBar | Operation::IntradayTick)
    )
}

/// If `request_tz` is set, interpret naive `start_datetime` / `end_datetime` in that zone and
/// rewrite as UTC ISO strings for Bloomberg.
pub(crate) async fn apply_intraday_request_timezone(
    engine: &Engine,
    params: &mut RequestParams,
) -> Result<(), BlpAsyncError> {
    if !intraday_operation(params) {
        return Ok(());
    }
    let Some(start) = params.start_datetime.clone() else {
        return Ok(());
    };
    let Some(end) = params.end_datetime.clone() else {
        return Ok(());
    };

    let label = match params.request_tz.as_deref() {
        None | Some("") => return Ok(()),
        Some(s) if s.eq_ignore_ascii_case("utc") => return Ok(()),
        Some(s) => s,
    };

    let iana = resolve_tz_label(engine, label, params.security.as_deref()).await?;

    let start_utc = wall_to_utc_iso(&start, &iana)?;
    let end_utc = wall_to_utc_iso(&end, &iana)?;
    params.start_datetime = Some(start_utc);
    params.end_datetime = Some(end_utc);
    Ok(())
}

fn wall_to_utc_iso(input: &str, wall_tz_iana: &str) -> Result<String, BlpAsyncError> {
    match parse_user_datetime(input)? {
        UserDateTime::Utc(dt) => Ok(format_utc_iso(&dt.with_timezone(&Utc))),
        UserDateTime::Naive(naive) => {
            let tz: Tz = wall_tz_iana
                .parse()
                .map_err(|_| BlpAsyncError::ConfigError {
                    detail: format!("invalid IANA timezone: {wall_tz_iana}"),
                })?;
            let local = tz.from_local_datetime(&naive).single().ok_or_else(|| {
                BlpAsyncError::ConfigError {
                    detail: format!("ambiguous or invalid local datetime: {input}"),
                }
            })?;
            let utc = local.with_timezone(&Utc);
            Ok(format_utc_iso(&utc))
        }
    }
}

enum UserDateTime {
    Utc(DateTime<Utc>),
    Naive(NaiveDateTime),
}

fn parse_user_datetime(input: &str) -> Result<UserDateTime, BlpAsyncError> {
    let t = input.trim().replace(' ', "T");

    if let Ok(dt) = DateTime::parse_from_rfc3339(&t) {
        return Ok(UserDateTime::Utc(dt.with_timezone(&Utc)));
    }

    let t_z = if t.ends_with('Z') && !t.contains('+') {
        format!("{}+00:00", t.trim_end_matches('Z'))
    } else {
        t.clone()
    };
    if let Ok(dt) = DateTime::parse_from_rfc3339(&t_z) {
        return Ok(UserDateTime::Utc(dt.with_timezone(&Utc)));
    }

    for fmt in [
        "%Y-%m-%dT%H:%M:%S%.f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ] {
        if let Ok(n) = NaiveDateTime::parse_from_str(&t, fmt) {
            return Ok(UserDateTime::Naive(n));
        }
    }

    if let Ok(d) = NaiveDate::parse_from_str(&t, "%Y-%m-%d") {
        let Some(n) = d.and_hms_opt(0, 0, 0) else {
            return Err(BlpAsyncError::ConfigError {
                detail: format!("invalid date: {input}"),
            });
        };
        return Ok(UserDateTime::Naive(n));
    }

    Err(BlpAsyncError::ConfigError {
        detail: format!("could not parse datetime: {input}"),
    })
}

fn format_utc_iso(dt: &DateTime<Utc>) -> String {
    let base = dt.format("%Y-%m-%dT%H:%M:%S").to_string();
    let micros = dt.timestamp_subsec_micros();
    if micros == 0 {
        base
    } else {
        format!("{base}.{:06}", micros)
    }
}

/// Relabel `time` column from UTC to `output_tz` (same instants; Arrow tz metadata only).
pub(crate) async fn apply_intraday_output_timezone(
    engine: &Engine,
    batch: RecordBatch,
    params: &RequestParams,
) -> Result<RecordBatch, BlpAsyncError> {
    if !intraday_operation(params) {
        return Ok(batch);
    }
    let label = match params.output_tz.as_deref() {
        None | Some("") => return Ok(batch),
        Some(s) if s.eq_ignore_ascii_case("utc") => return Ok(batch),
        Some(s) => s,
    };

    let iana = resolve_tz_label(engine, label, params.security.as_deref()).await?;
    apply_output_timezone_batch(batch, &iana).map_err(|e| BlpAsyncError::ConfigError {
        detail: format!("intraday output timezone: {e}"),
    })
}

pub(crate) fn apply_output_timezone_batch(
    batch: RecordBatch,
    iana: &str,
) -> Result<RecordBatch, ArrowError> {
    if iana == "UTC" {
        return Ok(batch);
    }

    let schema = batch.schema();
    let Some(ti) = schema.fields().iter().position(|f| f.name() == "time") else {
        return Ok(batch);
    };

    let col = batch.column(ti);
    let DataType::Timestamp(unit, Some(_)) = col.data_type() else {
        return Ok(batch);
    };
    if *unit != TimeUnit::Microsecond {
        return Ok(batch);
    }

    let ts = col
        .as_any()
        .downcast_ref::<TimestampMicrosecondArray>()
        .ok_or_else(|| {
            ArrowError::ComputeError("time column: expected TimestampMicrosecondArray".to_string())
        })?;

    let new_ts = ts.clone().with_timezone(iana);
    let new_field = Field::new("time", new_ts.data_type().clone(), true);
    let mut fields: Vec<_> = schema.fields().to_vec();
    fields[ti] = std::sync::Arc::new(new_field);
    let new_schema = arrow::datatypes::Schema::new_with_metadata(fields, schema.metadata().clone());
    let mut cols = batch.columns().to_vec();
    cols[ti] = std::sync::Arc::new(new_ts) as arrow::array::ArrayRef;
    RecordBatch::try_new(std::sync::Arc::new(new_schema), cols)
}

/// Resolve `output_tz` to an IANA name when relabeling is needed (`None` = keep UTC metadata).
pub(crate) async fn resolve_output_tz_iana(
    engine: &Engine,
    params: &RequestParams,
) -> Result<Option<String>, BlpAsyncError> {
    if !intraday_operation(params) {
        return Ok(None);
    }
    let label = match params.output_tz.as_deref() {
        None | Some("") => return Ok(None),
        Some(s) if s.eq_ignore_ascii_case("utc") => return Ok(None),
        Some(s) => s,
    };
    let iana = resolve_tz_label(engine, label, params.security.as_deref()).await?;
    if iana == "UTC" {
        return Ok(None);
    }
    Ok(Some(iana))
}

/// Map each streamed batch through [`apply_output_timezone_batch`] when `tz` is set.
pub(crate) fn wrap_batch_stream_with_output_tz(
    mut inner: mpsc::Receiver<Result<RecordBatch, BlpError>>,
    tz: Option<String>,
) -> mpsc::Receiver<Result<RecordBatch, BlpError>> {
    let Some(tz) = tz else {
        return inner;
    };
    let (tx, rx) = mpsc::channel(32);
    tokio::spawn(async move {
        while let Some(item) = inner.recv().await {
            let mapped = match item {
                Ok(batch) => match apply_output_timezone_batch(batch, &tz) {
                    Ok(b) => Ok(b),
                    Err(e) => Err(BlpError::Internal {
                        detail: format!("intraday output timezone: {e}"),
                    }),
                },
                Err(e) => Err(e),
            };
            if tx.send(mapped).await.is_err() {
                break;
            }
        }
    });
    rx
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_rfc3339_utc() {
        let u = parse_user_datetime("2024-06-01T14:30:00+00:00").unwrap();
        match u {
            UserDateTime::Utc(dt) => assert_eq!(dt.timestamp(), 1717242600),
            UserDateTime::Naive(_) => panic!("expected utc"),
        }
    }

    #[test]
    fn wall_utc_identity() {
        let s = wall_to_utc_iso("2024-06-01 14:30:00", "UTC").unwrap();
        assert!(s.starts_with("2024-06-01T14:30"));
    }
}
