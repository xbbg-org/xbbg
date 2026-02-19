//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Types/DisplayFormats.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <iosfwd>
#include <string>
#include "BloombergTypes/Datetime.h"

using namespace std;

namespace BEmu
{
	class DisplayFormats
	{
		private:
			static string Format(const Datetime& dt, const char * format);

		public:
			static string ToYYYYMMddNoSeparatorsWithQuotes(const Datetime& date);
			static string ToMMddYYWithSlashes(const Datetime& date);
			static string ToYYYYMMDDWithDashes(const Datetime& date);

			static string FormatNumberNoSeparators(double dbl, int numDecimals = 0);
			static string FormatDate(const Datetime& date);
			static string FormatTimeZone(const Datetime& time);
			static string FormatDatetimeZone(const Datetime& datetime);

			static string MarketDataRequests_FormatDateZone(const Datetime& date);

			static string HistoricalOrReferenceRequests_FormatDate(const Datetime& date);
			static bool HistoricalOrReferenceRequests_TryParseInput(const string& str, Datetime & dt);

			static string IntradayRequests_FormatDatetime(const Datetime& date);
			static string IntradayRequests_FormatDatetime_SecondsLast(const Datetime& datetime);
	};
}