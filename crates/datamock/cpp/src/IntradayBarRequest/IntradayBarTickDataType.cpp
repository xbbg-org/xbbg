//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarTickDataType.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Datetime.h"
#include "IntradayBarRequest/IntradayBarTickDataType.h"

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarTickDataType::IntradayBarTickDataType(const Datetime& dtTime, double open, double high, double low, double close, double value, long volume, int numEvents)
		{
			this->_open = open;
			this->_high = high;
			this->_low = low;
			this->_close = close;
			this->_value = value;
			this->_volume = volume;
			this->_numEvents = numEvents;

			this->_dtTime = dtTime;
		}

		IntradayBarTickDataType::~IntradayBarTickDataType()
		{
		}

		IntradayBarTickDataType::IntradayBarTickDataType(const IntradayBarTickDataType& arg)
		{
			this->_open = arg._open;
			this->_high = arg._high;
			this->_low = arg._low;
			this->_close = arg._close;
			this->_value = arg._value;
			this->_volume = arg._volume;
			this->_numEvents = arg._numEvents;
			
			this->_dtTime = arg._dtTime;
		}

		IntradayBarTickDataType& IntradayBarTickDataType::operator=(const IntradayBarTickDataType &rhs)
		{
			if (this != &rhs)
			{
				this->_open = rhs._open;
				this->_high = rhs._high;
				this->_low = rhs._low;
				this->_close = rhs._close;
				this->_value = rhs._value;
				this->_volume = rhs._volume;
				this->_numEvents = rhs._numEvents;
			
				this->_dtTime = rhs._dtTime;
			}
			return *this;
		}

		Datetime IntradayBarTickDataType::getDatetime() const
		{
			return this->_dtTime;
		}
		
		double IntradayBarTickDataType::getOpen() const
		{
			return this->_open;
		}

		double IntradayBarTickDataType::getHigh() const
		{
			return this->_high;
		}

		double IntradayBarTickDataType::getLow() const
		{
			return this->_low;
		}

		double IntradayBarTickDataType::getClose() const
		{
			return this->_close;
		}

		double IntradayBarTickDataType::getValue() const
		{
			return this->_value;
		}

		long IntradayBarTickDataType::getVolume() const
		{
			return this->_volume;
		}

		int IntradayBarTickDataType::getNumevents() const
		{
			return this->_numEvents;
		}
	}
}