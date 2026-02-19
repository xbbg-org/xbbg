//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickRequestElementString.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"

namespace BEmu
{
	class Name;

	namespace IntradayTickRequest
	{
		class IntradayTickRequestElementString : public ElementPtr
		{
			private:
				std::string _elementName, _value;
				std::stringstream _ss; //used for int and datetime constructors

			protected:
				IntradayTickRequestElementString(const std::string& elementName, int value);
				IntradayTickRequestElementString(const std::string& elementName, const Datetime& value);
				
			public:
				IntradayTickRequestElementString(const std::string& elementName, const std::string& value);
				virtual ~IntradayTickRequestElementString();
				const std::string& security() const;

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 0; }

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}