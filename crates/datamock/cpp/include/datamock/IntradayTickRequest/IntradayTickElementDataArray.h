//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickElementDataArray.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <map>
#include <vector>
#include "BloombergTypes/ElementPtr.h"

namespace BEmu
{
	class Name;
	class Datetime;

	namespace IntradayTickRequest
	{
		class IntradayTickElementData;
		class IntradayTickElementTuple3;

		class IntradayTickElementDataArray : public ElementPtr
		{
			private:
				std::vector< std::shared_ptr<IntradayTickElementData> > _tickData;

			public:
				IntradayTickElementDataArray(const std::map<Datetime, IntradayTickElementTuple3> ticks, bool includeConditionCodes);
				~IntradayTickElementDataArray();

				virtual std::shared_ptr<ElementPtr> getValueAsElement(int index) const;

				virtual Name name() const;

				virtual size_t numValues() const;
				virtual size_t numElements() const { return 0; }
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isArray() const { return true; }
				virtual bool isComplexType() const { return false; }

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}