//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketMessageSubscriptionStarted.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketMessageSubscriptionStarted.h"
#include <vector>
#include "Types/Rules.h"

#include "MarketDataRequest/MarketElementNull.h"
#include "MarketDataRequest/MarketElementExceptionsArray.h"
#include "MarketDataRequest/MarketElementSubscriptionStarted.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketMessageSubscriptionStarted::MarketMessageSubscriptionStarted(const Subscription& sub)
			: MessagePtr(Name("SubscriptionStarted"), sub.correlationId())
		{
            this->_correlationId = sub.correlationId();
			this->_topicName = sub.security();
			
            { //deal with bad fields
				std::vector<std::string> badFields, fields = sub.fieldList();

				for (int i = fields.size() - 1; i >= 0; i--)
				{
					if(Rules::IsBadField(fields[i]))
					{
						badFields.push_back(fields[i]);
						fields.erase(fields.begin() + i);
					}
				}

				if (badFields.size() == 0)
				{
					this->_exceptionsNull = std::shared_ptr<MarketElementNull>(new MarketElementNull("exceptions"));
					this->_exceptionsBadFields = std::shared_ptr<MarketElementExceptionsArray>();

					this->_isNull_exceptionsNull = false;
					this->_isNull_exceptionsBadFields = true;
				}
                else
				{
					this->_exceptionsNull = std::shared_ptr<MarketElementNull>();
					this->_exceptionsBadFields = std::shared_ptr<MarketElementExceptionsArray>(new MarketElementExceptionsArray(badFields));

					this->_isNull_exceptionsNull = true;
					this->_isNull_exceptionsBadFields = false;
				}
			}
		}

		MarketMessageSubscriptionStarted::~MarketMessageSubscriptionStarted()
		{
		}

		std::shared_ptr<ElementPtr> MarketMessageSubscriptionStarted::firstElement() const
		{
			if(!this->_isNull_exceptionsNull)
				return std::dynamic_pointer_cast<ElementPtr>(this->_exceptionsNull);

			else if(!this->_isNull_exceptionsBadFields)
				return std::dynamic_pointer_cast<ElementPtr>(this->_exceptionsBadFields);

			else
				throw messageEx;
		}

		bool MarketMessageSubscriptionStarted::hasElement(const char* name, bool excludeNullElements) const
		{
			if(!this->_isNull_exceptionsNull && this->_exceptionsNull->name() == name)
				return true;

			else if(!this->_isNull_exceptionsBadFields && this->_exceptionsBadFields->name() == name)
				return true;

			return false;
		}

		std::shared_ptr<ElementPtr> MarketMessageSubscriptionStarted::getElement(const char* name) const
		{
			if(!this->_isNull_exceptionsNull && this->_exceptionsNull->name() == name)
				return std::dynamic_pointer_cast<ElementPtr>(this->_exceptionsNull);

			else if(!this->_isNull_exceptionsBadFields && this->_exceptionsBadFields->name() == name)
				return std::dynamic_pointer_cast<ElementPtr>(this->_exceptionsBadFields);

			else
				throw messageEx;
		}

		size_t MarketMessageSubscriptionStarted::numElements() const
		{
			return 1;
		}

		std::shared_ptr<ElementPtr> MarketMessageSubscriptionStarted::asElement() const
		{
			throw messageEx;
		}

		const char* MarketMessageSubscriptionStarted::topicName() const
		{
			return this->_topicName.c_str();
		}

		std::ostream& MarketMessageSubscriptionStarted::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			if(!this->_isNull_exceptionsNull)
			{
				stream << "SubscriptionStarted = {" << std::endl << "}" << std::endl;
			}
			else if(!this->_isNull_exceptionsBadFields)
			{
				stream << "SubscriptionStarted = {" << std::endl;
				this->_exceptionsBadFields->print(stream, level + 1, spacesPerLevel);
				stream << "}" << std::endl;
			}
			else
				throw messageEx;

			return stream;
		}

	}
}