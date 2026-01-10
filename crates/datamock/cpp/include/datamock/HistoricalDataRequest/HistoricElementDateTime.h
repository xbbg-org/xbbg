//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricElementDateTime.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include "Types/CanConvertToStringType.h"

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		class HistoricElementDateTime : public ElementPtr, public CanConvertToStringType
		{
			private:
				Datetime _value;

			public:
				HistoricElementDateTime(const Datetime& value);
				~HistoricElementDateTime();

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 0; }
		
				virtual bool isNull() const { return false; }
				virtual bool isArray() const { return false; }
				virtual bool isComplexType() const { return false; }
				
				virtual Datetime getValueAsDatetime(int index) const;
				virtual const char * getValueAsString(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}