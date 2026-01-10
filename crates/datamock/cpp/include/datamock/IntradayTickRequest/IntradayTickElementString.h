//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickElementString.h" company="Jordan Robinson">
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
	class Name;

	namespace IntradayTickRequest
	{
		class IntradayTickElementString : public ElementPtr, public CanConvertToStringType
		{
			private:
				std::string _value;
				std::string _name;

			public:
				IntradayTickElementString(const std::string& name, const std::string& value);
				~IntradayTickElementString();

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 0; }
		
				virtual bool isArray() const { return false; }
				virtual bool isComplexType() const { return false; }

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;
				virtual const char * getValueAsString(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}