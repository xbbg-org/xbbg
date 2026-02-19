//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequestElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequestElementInt.h"

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequestElementInt::HistoricRequestElementInt(const std::string& elementName, int value) : 
			HistoricRequestElementString(elementName, value)
		{
			this->_ivalue = value;
		}

		HistoricRequestElementInt::~HistoricRequestElementInt()
		{
		}

		int HistoricRequestElementInt::getInt() const
		{
			return this->_ivalue;
		}

	}
}