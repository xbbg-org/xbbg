//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarElementLong.h" company="Jordan Robinson">
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

	namespace IntradayBarRequest
	{
		class IntradayBarElementLong : public ElementPtr
		{
			private:
				long _value;
				std::string _name;

			public:
				IntradayBarElementLong(const std::string& name, long value);
				~IntradayBarElementLong();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual long getValueAsInt64(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}