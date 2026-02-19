//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Datetime.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Datetime.h"
#include "Types/DisplayFormats.h"
#include <ctime>
#include <chrono>
#include <ostream>

namespace BEmu
{
Datetime::Datetime() : _year(1), _month(1), _day(1), _hours(0), _minutes(0), _seconds(0), _milliseconds(0), _microseconds(0), _dateTimeType(neither), _parts(0) {}
    Datetime::Datetime(unsigned year, unsigned month, unsigned day) : _year(year), _month(month), _day(day), _hours(0), _minutes(0), _seconds(0), _milliseconds(0), _microseconds(0) { setDateTimeType(date); }
    Datetime::Datetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds) : _year(year), _month(month), _day(day), _hours(hours), _minutes(minutes), _seconds(seconds), _milliseconds(0), _microseconds(0) { setDateTimeType(both); }
    Datetime::Datetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds, unsigned ms) : _year(year), _month(month), _day(day), _hours(hours), _minutes(minutes), _seconds(seconds), _milliseconds(ms), _microseconds(0) { setDateTimeType(both); }
    Datetime::Datetime(unsigned hours, unsigned minutes, unsigned seconds, unsigned ms) : _year(1), _month(1), _day(1), _hours(hours), _minutes(minutes), _seconds(seconds), _milliseconds(ms), _microseconds(0) { setDateTimeType(time); }
    Datetime::Datetime(const Datetime& arg) : _year(arg._year), _month(arg._month), _day(arg._day), _hours(arg._hours), _minutes(arg._minutes), _seconds(arg._seconds), _milliseconds(arg._milliseconds), _microseconds(arg._microseconds), _dateTimeType(arg._dateTimeType), _parts(arg._parts) {}

    Datetime Datetime::createDatetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds) { return Datetime(year, month, day, hours, minutes, seconds); }
    Datetime Datetime::createDate(unsigned year, unsigned month, unsigned day) { return Datetime(year, month, day); }
    Datetime Datetime::createTime(unsigned hours, unsigned minutes, unsigned seconds) { return Datetime(hours, minutes, seconds, 0); }
    Datetime Datetime::createTime(unsigned hours, unsigned minutes, unsigned seconds, unsigned ms) { return Datetime(hours, minutes, seconds, ms); }

    void Datetime::setDate(unsigned year, unsigned month, unsigned day) { _year = year; _month = month; _day = day; setDateTimeType(date); }
    void Datetime::setTime(unsigned hours, unsigned minutes, unsigned seconds) { _hours = hours; _minutes = minutes; _seconds = seconds; _milliseconds = 0; setDateTimeType(time); }
    void Datetime::setTime(unsigned hours, unsigned minutes, unsigned seconds, unsigned ms) { _hours = hours; _minutes = minutes; _seconds = seconds; _milliseconds = ms; setDateTimeType(time); }
    void Datetime::setDatetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds, unsigned ms) { _year = year; _month = month; _day = day; _hours = hours; _minutes = minutes; _seconds = seconds; _milliseconds = ms; }

    void Datetime::setYear(unsigned v) { _year = v; _parts |= DatetimeParts::YEAR; }
    void Datetime::setMonth(unsigned v) { _month = v; _parts |= DatetimeParts::MONTH; }
    void Datetime::setDay(unsigned v) { _day = v; _parts |= DatetimeParts::DAY; }
    void Datetime::setHours(unsigned v) { _hours = v; _parts |= DatetimeParts::HOURS; }
    void Datetime::setMinutes(unsigned v) { _minutes = v; _parts |= DatetimeParts::MINUTES; }
    void Datetime::setSeconds(unsigned v) { _seconds = v; _parts |= DatetimeParts::SECONDS; }
void Datetime::setMilliseconds(unsigned v) { _milliseconds = v; _parts |= DatetimeParts::MILLISECONDS; }
    void Datetime::setMicroseconds(unsigned v) { _microseconds = v; _parts |= DatetimeParts::MICROSECONDS; }

    Datetime& Datetime::operator=(const Datetime &rhs) {
        if (this != &rhs) { _year = rhs._year; _month = rhs._month; _day = rhs._day; _hours = rhs._hours; _minutes = rhs._minutes; _seconds = rhs._seconds; _milliseconds = rhs._milliseconds; _microseconds = rhs._microseconds; _dateTimeType = rhs._dateTimeType; _parts = rhs._parts; }
        return *this;
    }
    Datetime::~Datetime() {}

    Datetime Datetime::Today() {
        auto now = std::chrono::system_clock::now();
        std::time_t t = std::chrono::system_clock::to_time_t(now);
        std::tm tm;
#ifdef _WIN32
        localtime_s(&tm, &t);
#else
        localtime_r(&t, &tm);
#endif
        return Datetime(tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday);
    }

    Datetime Datetime::Now() {
        auto now = std::chrono::system_clock::now();
        std::time_t t = std::chrono::system_clock::to_time_t(now);
        std::tm tm;
#ifdef _WIN32
        localtime_s(&tm, &t);
#else
        localtime_r(&t, &tm);
#endif
        return Datetime(tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec);
    }

    Datetime Datetime::FromYYMMDD(const std::string& str) { return FromYYYYMMDD("20" + str); }
    Datetime Datetime::FromYYYYMMDD(const std::string& str) {
        Datetime result;
        if (DisplayFormats::HistoricalOrReferenceRequests_TryParseInput(str, result)) return result;
        throw result.datetimeEx;
    }

    void Datetime::setDateTimeType(DateTimeTypeEnum t) { _dateTimeType = t; _parts = (unsigned)t; }

    Datetime::WeekDayEnum Datetime::getWeekDay() const {
        int y = _year, m = _month, d = _day;
        if (m < 3) { m += 12; y--; }
        int k = y % 100, j = y / 100;
        int h = (d + (13 * (m + 1)) / 5 + k + k / 4 + j / 4 - 2 * j) % 7;
        return static_cast<WeekDayEnum>(((h + 6) % 7));
    }

    void Datetime::addYears(int y) { _year += y; _parts |= DatetimeParts::YEAR; }
    void Datetime::addMonths(int months) {
        int t = (_year * 12) + (_month - 1) + months;
        _year = t / 12;
        _month = (t % 12) + 1;
        _parts |= DatetimeParts::MONTH;
    }

    void Datetime::addDays(long days) {
        if (_dateTimeType == time) _dateTimeType = both;
        while (days > 0) {
            unsigned dim = 31;
            if (_month == 4 || _month == 6 || _month == 9 || _month == 11) dim = 30;
            else if (_month == 2) dim = isLeapYear(_year) ? 29 : 28;
            unsigned left = dim - _day;
            if (days <= (long)left) { _day += (unsigned)days; days = 0; }
            else { days -= (left + 1); _day = 1; _month++; if (_month > 12) { _month = 1; _year++; } }
        }
        while (days < 0) {
            if ((long)_day + days > 0) { _day += (unsigned)days; days = 0; }
            else {
                days += _day; _month--;
                if (_month < 1) { _month = 12; _year--; }
                unsigned dim = 31;
                if (_month == 4 || _month == 6 || _month == 9 || _month == 11) dim = 30;
                else if (_month == 2) dim = isLeapYear(_year) ? 29 : 28;
                _day = dim;
            }
        }
        _parts |= DatetimeParts::DAY;
    }

    void Datetime::addHours(long hours) {
        if (_dateTimeType == date) _dateTimeType = both;
        long tot = _hours + hours;
        long d = tot >= 0 ? tot / 24 : (tot - 23) / 24;
        _hours = (unsigned)((tot % 24 + 24) % 24);
        if (d != 0) addDays(d);
        _parts |= DatetimeParts::HOURS;
    }

    void Datetime::addMinutes(long minutes) {
        if (_dateTimeType == date) _dateTimeType = both;
        long tot = _minutes + minutes;
        long h = tot >= 0 ? tot / 60 : (tot - 59) / 60;
        _minutes = (unsigned)((tot % 60 + 60) % 60);
        if (h != 0) addHours(h);
        _parts |= DatetimeParts::MINUTES;
    }

    void Datetime::addSeconds(long seconds) {
        if (_dateTimeType == date) _dateTimeType = both;
        long tot = _seconds + seconds;
        long m = tot >= 0 ? tot / 60 : (tot - 59) / 60;
        _seconds = (unsigned)((tot % 60 + 60) % 60);
        if (m != 0) addMinutes(m);
        _parts |= DatetimeParts::SECONDS;
    }

    unsigned Datetime::parts() const { return _parts; }
    bool Datetime::hasParts(unsigned p) const { return (_parts & p) > 0; }
    bool Datetime::isValid() const { return true; }
    bool Datetime::isLeapYear(int y) { return 0 == y % 4 && (y <= 1752 || 0 != y % 100 || 0 == y % 400); }

    unsigned Datetime::year() const { return _year; }
    unsigned Datetime::month() const { return _month; }
    unsigned Datetime::day() const { return _day; }
    unsigned Datetime::hours() const { return _hours; }
    unsigned Datetime::minutes() const { return _minutes; }
    unsigned Datetime::seconds() const { return _seconds; }
unsigned Datetime::milliseconds() const { return _milliseconds; }
    unsigned Datetime::microseconds() const { return _microseconds; }

    std::ostream& operator<<(std::ostream& os, const Datetime& dt) {
        if (dt._dateTimeType == Datetime::date) os << DisplayFormats::FormatDate(dt);
        else if (dt._dateTimeType == Datetime::time) os << DisplayFormats::FormatTimeZone(dt);
        else if (dt._dateTimeType == Datetime::both) os << DisplayFormats::FormatDatetimeZone(dt);
        return os;
    }

    bool operator==(const Datetime& l, const Datetime& r) { return l._year == r._year && l._month == r._month && l._day == r._day && l._hours == r._hours && l._minutes == r._minutes && l._seconds == r._seconds; }
    bool operator!=(const Datetime& l, const Datetime& r) { return !(l == r); }
    bool operator<(const Datetime& l, const Datetime& r) {
        if (l._year != r._year) return l._year < r._year;
        if (l._month != r._month) return l._month < r._month;
        if (l._day != r._day) return l._day < r._day;
        if (l._hours != r._hours) return l._hours < r._hours;
        if (l._minutes != r._minutes) return l._minutes < r._minutes;
        return l._seconds < r._seconds;
    }
    bool operator<=(const Datetime& l, const Datetime& r) { return (l < r) || (l == r); }
    bool operator>(const Datetime& l, const Datetime& r) { return !(l <= r); }
    bool operator>=(const Datetime& l, const Datetime& r) { return !(l < r); }

    bool Datetime::isValidDate(int y, int mo, int d) {
        if ((y <= 0) || (y > 9999) || (mo <= 0) || (mo > 12) || (d <= 0) || (d > 31)) return false;
        if (d < 29) return true;
        if (y == 1752 && mo == 9 && d > 2 && d < 14) return false;
        switch (mo) {
            case 1: case 3: case 5: case 7: case 8: case 10: case 12: return true;
            case 4: case 6: case 9: case 11: return d <= 30;
            case 2: return isLeapYear(y) ? (d <= 29) : (d <= 28);
            default: return true;
        }
    }

    bool Datetime::isValidTime(int h, int m, int s) { return h >= 0 && h < 24 && m >= 0 && m < 60 && s >= 0 && s < 60; }
    bool Datetime::isValidTime(int h, int m, int s, int ms) { return isValidTime(h, m, s) && ms >= 0 && ms < 1000; }
}
