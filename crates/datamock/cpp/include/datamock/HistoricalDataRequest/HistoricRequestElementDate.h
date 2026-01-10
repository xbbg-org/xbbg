//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricRequestElementDate.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "HistoricalDataRequest/HistoricRequestElementString.h"

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		class HistoricRequestElementDate : public HistoricRequestElementString
		{
			private:
				Datetime _instance;

			public:
				HistoricRequestElementDate(const std::string& elementName);
				HistoricRequestElementDate(const std::string& elementName, const Datetime& datetime);
				~HistoricRequestElementDate();

				Datetime getDatetime() const;
		};
	}
}