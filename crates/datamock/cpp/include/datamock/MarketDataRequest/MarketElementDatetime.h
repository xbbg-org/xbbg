//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketElementDatetime.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Datetime.h"

namespace BEmu
{
	namespace MarketDataRequest
	{
		class MarketElementDatetime : public ElementPtr
		{
			private:
				std::string _name;
				Datetime _datetime;

			public:
				MarketElementDatetime(const std::string& name, const Datetime& datetime);

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isNull() const;

				virtual Datetime getValueAsDatetime(int index) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}