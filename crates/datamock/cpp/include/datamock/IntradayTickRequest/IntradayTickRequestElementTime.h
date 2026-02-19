//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickRequestElementTime.h" company="Jordan Robinson">
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

	namespace IntradayTickRequest
	{
		class IntradayTickRequestElementTime : public ElementPtr, public CanConvertToStringType
		{
			private:
				Datetime _instance;
				std::string _elementName;

			public:
				IntradayTickRequestElementTime(const std::string& elementName, const Datetime& date);
				~IntradayTickRequestElementTime();

				Datetime getDate() const;

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 0; }

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}