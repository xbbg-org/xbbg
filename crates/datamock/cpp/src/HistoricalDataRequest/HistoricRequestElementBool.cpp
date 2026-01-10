//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequestElementBool.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequestElementBool.h"

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequestElementBool::HistoricRequestElementBool(const std::string& elementName, bool bvalue) : HistoricRequestElementString(elementName, bvalue ? "true" : "false")
		{
			this->_bvalue = bvalue;
		}

		HistoricRequestElementBool::~HistoricRequestElementBool()
		{
		}

		bool HistoricRequestElementBool::getBool() const
		{
			return this->_bvalue;
		}
	}
}