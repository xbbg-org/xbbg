//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickElementDataParent.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <map>
#include "BloombergTypes/ElementPtr.h"

namespace BEmu
{
	class Name;
	class Datetime;
	class ElementPtr;

	namespace IntradayTickRequest
	{
		class IntradayTickElementDataArray;
		class IntradayTickElementTuple3;

		class IntradayTickElementDataParent : public ElementPtr
		{
			private:
				std::shared_ptr<IntradayTickElementDataArray> _array;

			public:
				using ElementPtr::getElement;

				IntradayTickElementDataParent(const std::map<Datetime, IntradayTickElementTuple3>& ticks, bool includeConditionCodes);
				~IntradayTickElementDataParent();

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 1; }		
				virtual bool isArray() const { return false; }
				virtual bool isComplexType() const { return true; }
				virtual SchemaElementDefinition elementDefinition() const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}