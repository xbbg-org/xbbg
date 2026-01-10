//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketMessageSubscriptionData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketMessageSubscriptionData.h"
#include "MarketDataRequest/MarketElementDouble.h"
#include "MarketDataRequest/MarketElementDatetime.h"
#include "MarketDataRequest/MarketElementInt.h"
#include "MarketDataRequest/MarketElementString.h"
#include "MarketDataRequest/MarketElementBool.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketMessageSubscriptionData::MarketMessageSubscriptionData(const Subscription& sub, const std::map<std::string, ObjectType>& fields)
			: MessagePtr(Name("MarketDataEvents"), sub.correlationId())
		{
			for(std::map<std::string, ObjectType>::const_iterator iter = fields.begin(); iter != fields.end(); ++iter)
			{
				std::string str = iter->first;
				ObjectType field = iter->second;

				if(!field.IsNull())
				{
					//all deleted in destructor
					switch(field.GetType())
					{
						case ObjectType::eDouble:
						{
							std::shared_ptr<MarketElementDouble> elmP(new MarketElementDouble(str, field.ValueAsDouble()));
							std::shared_ptr<ElementPtr> elm(std::dynamic_pointer_cast<ElementPtr>(elmP));

							this->_fields[str] = elm;
						}
						break;
						case ObjectType::eDatetime:
						{
							std::shared_ptr<MarketElementDatetime> elmP(new MarketElementDatetime(str, field.ValueAsDatetime()));
							std::shared_ptr<ElementPtr> elm(std::dynamic_pointer_cast<ElementPtr>(elmP));
						
							this->_fields[str] = elm;
						}
						break;
						case ObjectType::eString:
						{
							std::shared_ptr<MarketElementString> elmP(new MarketElementString(str, field.ValueAsString()));
							std::shared_ptr<ElementPtr> elm(std::dynamic_pointer_cast<ElementPtr>(elmP));
						
							this->_fields[str] = elm;
						}
						break;
						case ObjectType::eInt:
						{
							std::shared_ptr<MarketElementInt> elmP(new MarketElementInt(str, field.ValueAsInt()));
							std::shared_ptr<ElementPtr> elm(std::dynamic_pointer_cast<ElementPtr>(elmP));
						
							this->_fields[str] = elm;
						}
						break;
					case ObjectType::eBool:
						{
							std::shared_ptr<MarketElementBool> elmP(new MarketElementBool(str, field.ValueAsBool()));
							std::shared_ptr<ElementPtr> elm(std::dynamic_pointer_cast<ElementPtr>(elmP));
						
							this->_fields[str] = elm;
						}
						break;
						case ObjectType::eChainTickers:
						case ObjectType::eNothing:
							// Not applicable for market data subscriptions
							break;
					}
				}
			}
			this->_security = sub.security();
		}

		MarketMessageSubscriptionData::~MarketMessageSubscriptionData()
		{
			this->_fields.clear();
		}

		const char* MarketMessageSubscriptionData::topicName() const
		{
			return this->_security.c_str();
		}

		size_t MarketMessageSubscriptionData::numElements() const
		{
			return this->_fields.size();
		}

		bool MarketMessageSubscriptionData::hasElement(const char* name, bool excludeNullElements) const
		{
			return this->_fields.find(name) != this->_fields.end();
		}

		std::shared_ptr<ElementPtr> MarketMessageSubscriptionData::getElement(const char* name) const
		{
			for(std::map<std::string, std::shared_ptr<ElementPtr> >::const_iterator iter = this->_fields.begin(); iter != this->_fields.end(); ++iter)
			{
				std::string key = iter->first;

				if(key == name)
				{
					std::shared_ptr<ElementPtr> result = iter->second;
					return result;
				}
			}
			throw messageEx;
		}

		std::ostream& MarketMessageSubscriptionData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "MarketDataEvents = {" << std::endl;
			
			for(std::map<std::string, std::shared_ptr<ElementPtr> >::const_iterator iter = this->_fields.begin(); iter != this->_fields.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = iter->second;
				elm->print(stream, level + 1, spacesPerLevel);
			}
			stream << "}" << std::endl;

			return stream;
		}

	}
}