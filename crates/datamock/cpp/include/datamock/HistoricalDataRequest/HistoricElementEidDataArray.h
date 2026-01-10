//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricElementEidDataArray.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include <vector>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		class HistoricElementEidDataArray : public ElementPtr
		{
			private:
				std::vector<int> _eids;

			public:
				HistoricElementEidDataArray();
				~HistoricElementEidDataArray();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const { return 0; }
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isNull() const { return false; }
				virtual bool isArray() const { return true; }
				virtual bool isComplexType() const { return false; }

				virtual int getValueAsInt32(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}
