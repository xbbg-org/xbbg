use chrono::{DateTime, NaiveDate, NaiveDateTime, NaiveTime, TimeZone, Utc};
use chrono_tz::Tz;

use crate::{ExtError, Result};

use super::exchange::ExchangeInfo;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MarketTiming {
    Bod,
    Eod,
    Finished,
}

impl MarketTiming {
    pub fn from_str(value: &str) -> Option<Self> {
        match value.trim().to_ascii_uppercase().as_str() {
            "BOD" => Some(Self::Bod),
            "EOD" => Some(Self::Eod),
            "FINISHED" => Some(Self::Finished),
            _ => None,
        }
    }
}

/// Convert local exchange session timestamps to UTC.
pub fn session_times_to_utc(
    start_time: &str,
    end_time: &str,
    exchange_tz: &str,
    date: NaiveDate,
) -> Result<(DateTime<Utc>, DateTime<Utc>)> {
    if exchange_tz.eq_ignore_ascii_case("UTC") {
        let start_local = parse_hhmm(start_time)?;
        let end_local = parse_hhmm(end_time)?;
        let start_naive = NaiveDateTime::new(date, start_local);
        let end_naive = NaiveDateTime::new(date, end_local);
        return Ok((
            Utc.from_utc_datetime(&start_naive),
            Utc.from_utc_datetime(&end_naive),
        ));
    }

    let tz = parse_tz(exchange_tz)?;
    let start_dt = to_utc(date, parse_hhmm(start_time)?, tz)?;
    let end_dt = to_utc(date, parse_hhmm(end_time)?, tz)?;
    Ok((start_dt, end_dt))
}

/// Resolve market timing for a given date and optional target timezone.
pub fn market_timing(
    info: &ExchangeInfo,
    date: NaiveDate,
    timing: MarketTiming,
    target_tz: Option<&str>,
) -> Result<String> {
    let day =
        info.sessions.day.as_ref().ok_or_else(|| {
            ExtError::InvalidInput("missing day session in ExchangeInfo".to_string())
        })?;

    let session_time = match timing {
        MarketTiming::Bod => day.0.as_str(),
        MarketTiming::Eod => day.1.as_str(),
        MarketTiming::Finished => info
            .sessions
            .allday
            .as_ref()
            .map(|(_, end)| end.as_str())
            .unwrap_or(day.1.as_str()),
    };

    let local_time = parse_hhmm(session_time)?;

    match target_tz {
        None => Ok(format!("{} {}", date.format("%Y-%m-%d"), session_time)),
        Some(tz_name) if tz_name.eq_ignore_ascii_case("local") => {
            Ok(format!("{} {}", date.format("%Y-%m-%d"), session_time))
        }
        Some(tz_name) => {
            let src_tz = parse_tz(&info.timezone)?;
            let dst_tz = parse_tz(tz_name)?;
            let local_dt = src_tz
                .from_local_datetime(&NaiveDateTime::new(date, local_time))
                .single()
                .ok_or_else(|| {
                    ExtError::InvalidInput(format!(
                        "ambiguous/nonexistent local datetime in '{}' for {} {}",
                        info.timezone, date, session_time
                    ))
                })?;
            let converted = local_dt.with_timezone(&dst_tz);
            Ok(converted.format("%Y-%m-%d %H:%M:%S%:z").to_string())
        }
    }
}

fn parse_tz(value: &str) -> Result<Tz> {
    value
        .parse::<Tz>()
        .map_err(|_| ExtError::InvalidInput(format!("invalid timezone: {value}")))
}

fn parse_hhmm(value: &str) -> Result<NaiveTime> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(ExtError::InvalidInput("empty time string".to_string()));
    }

    if let Ok(v) = NaiveTime::parse_from_str(trimmed, "%H:%M") {
        return Ok(v);
    }
    if let Ok(v) = NaiveTime::parse_from_str(trimmed, "%H:%M:%S") {
        return Ok(v);
    }
    if trimmed.len() == 4 && trimmed.chars().all(|c| c.is_ascii_digit()) {
        let hh: u32 = trimmed[0..2]
            .parse()
            .map_err(|_| ExtError::InvalidInput(format!("invalid time: {value}")))?;
        let mm: u32 = trimmed[2..4]
            .parse()
            .map_err(|_| ExtError::InvalidInput(format!("invalid time: {value}")))?;
        return NaiveTime::from_hms_opt(hh, mm, 0)
            .ok_or_else(|| ExtError::InvalidInput(format!("invalid time: {value}")));
    }

    Err(ExtError::InvalidInput(format!("invalid time: {value}")))
}

fn to_utc(date: NaiveDate, time: NaiveTime, tz: Tz) -> Result<DateTime<Utc>> {
    let local = tz
        .from_local_datetime(&NaiveDateTime::new(date, time))
        .single()
        .ok_or_else(|| {
            ExtError::InvalidInput(format!(
                "ambiguous/nonexistent local datetime for {} {} in timezone {}",
                date,
                time.format("%H:%M:%S"),
                tz
            ))
        })?;
    Ok(local.with_timezone(&Utc))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::markets::exchange::{ExchangeInfo, ExchangeInfoSource};
    use crate::markets::sessions::SessionWindows;

    #[test]
    fn test_session_times_to_utc() {
        let date = NaiveDate::from_ymd_opt(2025, 11, 14).unwrap();
        let (s, e) = session_times_to_utc("09:30", "10:00", "America/New_York", date).unwrap();
        assert_eq!(s.format("%Y-%m-%dT%H:%M").to_string(), "2025-11-14T14:30");
        assert_eq!(e.format("%Y-%m-%dT%H:%M").to_string(), "2025-11-14T15:00");
    }

    #[test]
    fn test_market_timing_local_and_target_tz() {
        let info = ExchangeInfo {
            ticker: "AAPL US Equity".to_string(),
            mic: Some("XNGS".to_string()),
            exch_code: Some("US".to_string()),
            timezone: "America/New_York".to_string(),
            utc_offset: Some(-5.0),
            sessions: SessionWindows {
                day: Some(("09:30".to_string(), "16:00".to_string())),
                allday: Some(("04:00".to_string(), "20:00".to_string())),
                pre: None,
                post: None,
                am: None,
                pm: None,
            },
            source: ExchangeInfoSource::Bloomberg,
            cached_at: None,
        };
        let date = NaiveDate::from_ymd_opt(2025, 11, 14).unwrap();

        let local = market_timing(&info, date, MarketTiming::Eod, Some("local")).unwrap();
        assert_eq!(local, "2025-11-14 16:00");

        let london = market_timing(&info, date, MarketTiming::Eod, Some("Europe/London")).unwrap();
        assert!(london.starts_with("2025-11-14 21:00:00"));
    }
}
