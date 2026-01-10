//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Datetime.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include <exception>
#include <ctime>

namespace BEmu
{	
	class Datetime
	{
		public:
			struct DatetimeParts {
				enum Value {
					  YEAR            = 0x1
					, MONTH           = 0x2
					, DAY             = 0x4
					, OFFSET          = 0x8
					, HOURS           = 0x10
					, MINUTES         = 0x20
					, SECONDS         = 0x40
				, FRACSECONDS     = 0x80
					, MILLISECONDS    = 0x80
					, MICROSECONDS    = 0x100
					, DATE            = 0x7
					, TIME            = 0x70
					, TIMEFRACSECONDS = 0x1F0
					, TIMEMILLI       = 0xF0
				};
			};

		private:
unsigned _year, _month, _day;
			unsigned _hours, _minutes, _seconds, _milliseconds, _microseconds;
			
			enum DateTimeTypeEnum { neither = 0, date = DatetimeParts::DATE, time = DatetimeParts::TIME, both = DatetimeParts::DATE | DatetimeParts::TIME };
			DateTimeTypeEnum _dateTimeType;
			unsigned _parts;
			
			void setDateTimeType(DateTimeTypeEnum dateTimeType);
			void setDatetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds, unsigned milliseconds);

		public:
			enum WeekDayEnum
			{
				Sunday = 0,
				Monday = 1, 
				Tuesday = 2, 
				Wednesday = 3, 
				Thursday = 4, 
				Friday = 5, 
				Saturday = 6
			};

			class DatetimeException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} datetimeEx;

			WeekDayEnum getWeekDay() const;

			DLL_EXPORT Datetime();
			DLL_EXPORT Datetime(unsigned year, unsigned month, unsigned day);
			DLL_EXPORT Datetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds);
			DLL_EXPORT Datetime(unsigned hours, unsigned minutes, unsigned seconds, unsigned milleseconds);
			DLL_EXPORT Datetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds, unsigned milleseconds);

			DLL_EXPORT static Datetime createDatetime(unsigned year, unsigned month, unsigned day, unsigned hours, unsigned minutes, unsigned seconds);
			DLL_EXPORT static Datetime createDate(unsigned year, unsigned month, unsigned day);
			DLL_EXPORT static Datetime createTime(unsigned hours, unsigned minutes, unsigned seconds);
			DLL_EXPORT static Datetime createTime(unsigned hours, unsigned minutes, unsigned seconds, unsigned milliseconds);
			
			DLL_EXPORT Datetime& operator=(const Datetime &rhs);
			DLL_EXPORT Datetime(const Datetime& arg);

			DLL_EXPORT ~Datetime();
		
			DLL_EXPORT unsigned parts() const;
			DLL_EXPORT bool hasParts(unsigned parts) const;
			DLL_EXPORT bool isValid() const;

			DLL_EXPORT unsigned year() const;
			DLL_EXPORT unsigned month() const;
			DLL_EXPORT unsigned day() const;
			DLL_EXPORT unsigned hours() const;
			DLL_EXPORT unsigned minutes() const;
			DLL_EXPORT unsigned seconds() const;
DLL_EXPORT unsigned milliseconds() const;
			DLL_EXPORT unsigned microseconds() const;

			DLL_EXPORT void setYear(unsigned value);
			DLL_EXPORT void setMonth(unsigned value);
			DLL_EXPORT void setDay(unsigned value);
			DLL_EXPORT void setHours(unsigned value);
			DLL_EXPORT void setMinutes(unsigned value);
			DLL_EXPORT void setSeconds(unsigned value);
DLL_EXPORT void setMilliseconds(unsigned milliseconds);
			DLL_EXPORT void setMicroseconds(unsigned microseconds);

			DLL_EXPORT void setDate(unsigned year, unsigned month, unsigned day);
			DLL_EXPORT void setTime(unsigned hours, unsigned minutes, unsigned seconds);
			DLL_EXPORT void setTime(unsigned hours, unsigned minutes, unsigned seconds, unsigned milliseconds);

			void addYears(int years);
			void addMonths(int months);
			void addDays(long days);
			void addHours(long hours);
			void addMinutes(long minutes);
			void addSeconds(long seconds);
			
			static Datetime Today();
			static Datetime Now();
			static Datetime FromYYYYMMDD(const std::string& str);
			static Datetime FromYYMMDD(const std::string& str);

			DLL_EXPORT static bool isLeapYear(int year);
			DLL_EXPORT static bool isValidDate(int year, int month, int day);
			DLL_EXPORT static bool isValidTime(int hours, int minutes, int seconds);
			DLL_EXPORT static bool isValidTime(int hours, int minutes, int seconds, int milliSeconds);

			friend DLL_EXPORT bool operator<(const Datetime& lhs, const Datetime& rhs);
			friend DLL_EXPORT bool operator<=(const Datetime& lhs, const Datetime& rhs);
			friend DLL_EXPORT bool operator>(const Datetime& lhs, const Datetime& rhs);
			friend DLL_EXPORT bool operator>=(const Datetime& lhs, const Datetime& rhs);
			friend DLL_EXPORT bool operator==(const Datetime& lhs, const Datetime& rhs);
			friend DLL_EXPORT bool operator!=(const Datetime& lhs, const Datetime& rhs);
			
			friend DLL_EXPORT std::ostream& operator<<(std::ostream& os, const Datetime& datetime);
	};

	DLL_EXPORT bool operator<(const Datetime& lhs, const Datetime& rhs);
	DLL_EXPORT bool operator<=(const Datetime& lhs, const Datetime& rhs);
	DLL_EXPORT bool operator>(const Datetime& lhs, const Datetime& rhs);
	DLL_EXPORT bool operator>=(const Datetime& lhs, const Datetime& rhs);
	DLL_EXPORT bool operator==(const Datetime& lhs, const Datetime& rhs);
	DLL_EXPORT std::ostream& operator<<(std::ostream& os, const Datetime& datetime);
}
