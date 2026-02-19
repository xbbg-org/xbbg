//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarTickDataType.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

namespace BEmu
{
	class Datetime;

	namespace IntradayBarRequest
	{
		class IntradayBarTickDataType
		{
			private:
				Datetime _dtTime;
				double _open, _high, _low, _close, _value;
				long _volume;
				int _numEvents;

			public:
				IntradayBarTickDataType(const Datetime& dtTime, double open, double high, double low, double close, double value, long volume, int numEvents);
				~IntradayBarTickDataType();
				IntradayBarTickDataType(const IntradayBarTickDataType& arg);
				IntradayBarTickDataType& operator=(const IntradayBarTickDataType &rhs);

				Datetime getDatetime() const;
				double getOpen() const;
				double getHigh() const;
				double getLow() const;
				double getClose() const;
				double getValue() const;
				long getVolume() const;
				int getNumevents() const;
		};
	}
}