//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickRequestElementStringArray.h" company="Jordan Robinson">
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

	namespace IntradayTickRequest
	{
		class IntradayTickRequestElementStringArray : public ElementPtr
		{
			private:
				std::string _elementName;
				std::vector<std::string> _values;
				
			public:
				IntradayTickRequestElementStringArray(const std::string& elementName);
				~IntradayTickRequestElementStringArray();
				void addValue(const std::string& value);
				std::vector<std::string> getValues() const;

				virtual Name name() const;
				virtual size_t numValues() const { return 0; }
				virtual size_t numElements() const;
		
				virtual bool isArray() const { return true; }
				virtual bool isComplexType() const { return false; }
				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}