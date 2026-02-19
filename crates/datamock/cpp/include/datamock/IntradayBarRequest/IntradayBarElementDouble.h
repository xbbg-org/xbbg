//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarElementDouble.h" company="Jordan Robinson">
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

	namespace IntradayBarRequest
	{
		class IntradayBarElementDouble : public ElementPtr, public CanConvertToStringType
		{
			private:
				double _value;
				std::string _name;

			public:
				IntradayBarElementDouble(const std::string& name, double value);
				~IntradayBarElementDouble();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual double getValueAsFloat64(int index) const;
				virtual int getValueAsInt32(int index) const;
				virtual const char * getValueAsString(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}