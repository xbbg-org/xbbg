//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarElementData.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include <vector>

namespace BEmu
{
	class Name;

	namespace IntradayBarRequest
	{
		class IntradayBarTickDataType;
		class IntradayBarElementTickDataArray;

		class IntradayBarElementData : public ElementPtr
		{
			private:
				std::shared_ptr<IntradayBarElementTickDataArray> _array;

			public:
				using ElementPtr::getElement;

				IntradayBarElementData(const std::vector< std::shared_ptr<IntradayBarTickDataType> >& bars);
				~IntradayBarElementData();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}