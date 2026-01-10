//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricRequestElementInt.h" company="Jordan Robinson">
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
		class HistoricRequestElementInt : public HistoricRequestElementString
		{
			private:
				int _ivalue;

			public:
				HistoricRequestElementInt(const std::string& elementName, int value);
				~HistoricRequestElementInt();

				int getInt() const;
		};
	}
}