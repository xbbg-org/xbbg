//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarRequestElementBool.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include "Types/CanConvertToStringType.h"

namespace BEmu
{
	namespace IntradayBarRequest
	{
		class IntradayBarRequestElementBool : public ElementPtr, public CanConvertToStringType
		{
			private:
				bool _bvalue;
				std::string _elementName;

			public:
				IntradayBarRequestElementBool(const std::string& elementName, bool bvalue);
				~IntradayBarRequestElementBool();
				bool getBool() const;

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual const char * getValueAsString(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}