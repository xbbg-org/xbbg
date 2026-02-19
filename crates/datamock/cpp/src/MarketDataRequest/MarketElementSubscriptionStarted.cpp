//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementSubscriptionStarted.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementSubscriptionStarted.h"
#include "MarketDataRequest/MarketMessageSubscriptionStarted.h"
#include "MarketDataRequest/MarketElementNull.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementSubscriptionStarted::MarketElementSubscriptionStarted(const MarketMessageSubscriptionStarted& arg) :
			_exceptions( std::dynamic_pointer_cast<MarketElementNull>(arg.firstElement()) )
		{
		}

		Name MarketElementSubscriptionStarted::name() const
		{
			return Name("SubscriptionStarted");
		}

		size_t MarketElementSubscriptionStarted::numValues() const
		{
			return 1;
		}

		size_t MarketElementSubscriptionStarted::numElements() const
		{
			return 1;
		}

		bool MarketElementSubscriptionStarted::isNull() const
		{
			return false;
		}

		bool MarketElementSubscriptionStarted::isArray() const
		{
			return false;
		}

		bool MarketElementSubscriptionStarted::isComplexType() const
		{
			return true;
		}

		std::ostream& MarketElementSubscriptionStarted::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "SubscriptionStarted = {" << std::endl << '}' << std::endl;
			return stream;
		}
	}
}