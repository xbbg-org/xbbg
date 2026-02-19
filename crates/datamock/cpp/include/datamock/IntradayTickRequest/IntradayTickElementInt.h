//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickElementInt.h" company="Jordan Robinson">
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
		class IntradayTickElementInt : public ElementPtr, public CanConvertToStringType
		{
			private:
				int _value;
				std::string _name;

			public:
				IntradayTickElementInt(const std::string& name, int value);
				~IntradayTickElementInt();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual int getValueAsInt32(int index) const;
				virtual long getValueAsInt64(int index) const;
				virtual float getValueAsFloat32(int index) const;
				virtual double getValueAsFloat64(int index) const;
				virtual const char * getValueAsString(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}