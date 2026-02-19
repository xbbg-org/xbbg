//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/DisplayFormats.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Types/DisplayFormats.h"
#include <sstream>
#include <iomanip>

namespace BEmu
{
	string DisplayFormats::FormatNumberNoSeparators(double dbl, int numDecimals)
	{
		stringstream ss;
		ss << std::fixed << std::setprecision(numDecimals) << dbl << endl;
		return ss.str();
	}

	string DisplayFormats::ToYYYYMMddNoSeparatorsWithQuotes(const Datetime& date)
	{
		stringstream ss;
		ss << "\"" << date.year() << std::setfill('0') << std::setw(2) << date.month() << std::setw(2) << date.day() << "\"";
		return ss.str();
	}

	string DisplayFormats::ToMMddYYWithSlashes(const Datetime& date)
	{
		stringstream ss;
		ss << std::setfill('0') << std::setw(2) << date.month() << "/" << std::setw(2) << date.day() << "/" << std::setw(2) << (date.year() % 100);
		return ss.str();
	}

	string DisplayFormats::ToYYYYMMDDWithDashes(const Datetime& date)
	{
		stringstream ss;
		ss << date.year() << "-" << std::setfill('0') << std::setw(2) << date.month() << "-" << std::setw(2) << date.day();
		return ss.str();
	}

	string DisplayFormats::FormatDate(const Datetime& date)
	{
		return ToYYYYMMDDWithDashes(date);
	}

	string DisplayFormats::FormatTimeZone(const Datetime& time)
	{
		stringstream ss;
		ss << std::setfill('0') << std::setw(2) << time.hours() << ":" << std::setw(2) << time.minutes() << ":" << std::setw(2) << time.seconds() << ".000+00:00";
		return ss.str();
	}

	string DisplayFormats::FormatDatetimeZone(const Datetime& datetime)
	{
		stringstream ss;
		ss << datetime.year() << "-" << std::setfill('0') << std::setw(2) << datetime.month() << "-" << std::setw(2) << datetime.day();
		ss << "T" << std::setw(2) << datetime.hours() << ":" << std::setw(2) << datetime.minutes() << ":" << std::setw(2) << datetime.seconds() << ".000+00:00";
		return ss.str();
	}

	string DisplayFormats::MarketDataRequests_FormatDateZone(const Datetime& date)
	{
		stringstream ss;
		ss << date.year() << "-" << std::setfill('0') << std::setw(2) << date.month() << "-" << std::setw(2) << date.day() << "+00:00";
		return ss.str();
	}

	string DisplayFormats::HistoricalOrReferenceRequests_FormatDate(const Datetime& date)
	{
		return ToYYYYMMDDWithDashes(date);
	}

	bool DisplayFormats::HistoricalOrReferenceRequests_TryParseInput(const string& str, Datetime & dt)
	{
		try
		{
			int y = std::stoi(str.substr(0, 4));
			int m = std::stoi(str.substr(4, 2));
			int d = std::stoi(str.substr(6, 2));
			dt = Datetime(y, m, d);
			return true;
		}
		catch(...)
		{
			return false;
		}
	}

	string DisplayFormats::IntradayRequests_FormatDatetime(const Datetime& datetime)
	{
		stringstream ss;
		ss << datetime.year() << "-" << std::setfill('0') << std::setw(2) << datetime.month() << "-" << std::setw(2) << datetime.day();
		ss << "T" << std::setw(2) << datetime.hours() << ":" << std::setw(2) << datetime.minutes() << ":" << std::setw(2) << datetime.seconds() << ".000";
		return ss.str();
	}

	string DisplayFormats::IntradayRequests_FormatDatetime_SecondsLast(const Datetime& datetime)
	{
		stringstream ss;
		ss << datetime.year() << "-" << std::setfill('0') << std::setw(2) << datetime.month() << "-" << std::setw(2) << datetime.day();
		ss << "T" << std::setw(2) << datetime.hours() << ":" << std::setw(2) << datetime.minutes() << ":" << std::setw(2) << datetime.seconds();
		return ss.str();
	}
}
