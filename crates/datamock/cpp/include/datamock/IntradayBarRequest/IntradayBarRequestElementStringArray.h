//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarRequestElementStringArray.h" company="Jordan Robinson">
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
		class IntradayBarRequestElementStringArray : public ElementPtr
		{
			private:
				std::vector<std::string> _values;
				std::string _name;
				
				bool isEventTypeAllowed(const std::string& value);

			public:
				IntradayBarRequestElementStringArray(const std::string& elementName);
				~IntradayBarRequestElementStringArray();
				
				void addValue(const std::string& value);
				std::vector<std::string> values() const;

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}