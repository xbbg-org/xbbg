//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarRequestElementTime.h" company="Jordan Robinson">
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
	class Datetime;

	namespace IntradayBarRequest
	{
		class IntradayBarRequestElementTime : public ElementPtr, public CanConvertToStringType
		{
			private:
				Datetime _dtvalue;
				std::string _elementName;

			public:
				//IntradayBarRequestElementTime(const std::string& elementName);
				IntradayBarRequestElementTime(const std::string& elementName, const Datetime& dtvalue);
				~IntradayBarRequestElementTime();
				Datetime getDatetime() const;

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