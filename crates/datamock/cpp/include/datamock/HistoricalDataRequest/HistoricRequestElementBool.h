//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricRequestElementBool.h" company="Jordan Robinson">
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
		class HistoricRequestElementBool : public HistoricRequestElementString
		{
			private:
				bool _bvalue;

			public:
				HistoricRequestElementBool(const std::string& elementName, bool bvalue);
				~HistoricRequestElementBool();

				bool getBool() const;
		};
	}
}