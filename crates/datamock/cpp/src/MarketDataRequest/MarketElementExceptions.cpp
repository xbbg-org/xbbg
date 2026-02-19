//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementExceptions.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementExceptions.h"
#include "MarketDataRequest/MarketElementString.h"
#include "MarketDataRequest/MarketElementReason.h"

#include "Types/IndentType.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementExceptions::MarketElementExceptions(const std::string& badField) :
			_fieldId(new MarketElementString("fieldId", badField)),
			_reason(new MarketElementReason(MarketDataRequest::ReasonType::badField))
		{
		}

		MarketElementExceptions::~MarketElementExceptions()
		{
		}

		Name MarketElementExceptions::name() const
		{
			return Name("exceptions");
		}

		size_t MarketElementExceptions::numValues() const
		{
			return 1;
		}

		size_t MarketElementExceptions::numElements() const
		{
			return 2;
		}

		SchemaElementDefinition MarketElementExceptions::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("SubscriptionException"));
			return result;
		}

		bool MarketElementExceptions::isNull() const
		{
			return false;
		}

		bool MarketElementExceptions::isArray() const
		{
			return false;
		}

		bool MarketElementExceptions::isComplexType() const
		{
			return true;
		}

		std::shared_ptr<ElementPtr> MarketElementExceptions::getElement(const char* name) const
		{
			if(strncmp(name, "fieldId", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_fieldId);
			
			else if(strncmp(name, "reason", 7) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_reason);

			else
				throw elementPtrEx;
		}

		bool MarketElementExceptions::hasElement(const char* name, bool excludeNullElements) const
		{
			return strncmp(name, "fieldId", 8) == 0 || strncmp(name, "reason", 7) == 0;
		}

		const char* MarketElementExceptions::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::ostream& MarketElementExceptions::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "exceptions = {" << std::endl;
			
			this->_fieldId->print(stream, level + 1);
			this->_reason->print(stream, level + 1);

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}