//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementSubscriptionCancelReason.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementSubscriptionCancelReason.h"
#include "MarketDataRequest/MarketElementString.h"
#include "MarketDataRequest/MarketElementInt.h"

#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementSubscriptionCancelReason::MarketElementSubscriptionCancelReason() :
            _source(new MarketElementString("source", "Session")),
            _category(new MarketElementString("category", "CANCELED")),
            _description(new MarketElementString("description", "Subscription canceled")),
            _subCategory(new MarketElementString("subcategory", "")),
            _errorCode(new MarketElementInt("errorCode", 0))
		{
		}

		MarketElementSubscriptionCancelReason::~MarketElementSubscriptionCancelReason()
		{
		}

		Name MarketElementSubscriptionCancelReason::name() const
		{
			return Name("reason");
		}

		size_t MarketElementSubscriptionCancelReason::numValues() const
		{
			return 1;
		}

		size_t MarketElementSubscriptionCancelReason::numElements() const
		{
			return 5;
		}

		bool MarketElementSubscriptionCancelReason::isNull() const
		{
			return false;
		}

		bool MarketElementSubscriptionCancelReason::isArray() const
		{
			return false;
		}

		bool MarketElementSubscriptionCancelReason::isComplexType() const
		{
			return true;
		}

		std::ostream& MarketElementSubscriptionCancelReason::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "reason = {" << std::endl;
			this->_source->print(stream, level + 1, spacesPerLevel);
			this->_errorCode->print(stream, level + 1, spacesPerLevel);
			this->_category->print(stream, level + 1, spacesPerLevel);
			this->_description->print(stream, level + 1, spacesPerLevel);
			this->_subCategory->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}