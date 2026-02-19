//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/MarketDataRequest/MarketElementExceptionsArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "MarketDataRequest/MarketElementExceptionsArray.h"
#include "MarketDataRequest/MarketElementExceptions.h"

#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace MarketDataRequest
	{
		MarketElementExceptionsArray::MarketElementExceptionsArray(const std::vector<std::string>& badFields)
		{
			for(std::vector<std::string>::const_iterator iter = badFields.begin(); iter != badFields.end(); ++iter)
			{
				std::string badField = *iter;
				this->_exceptions.push_back( std::shared_ptr<MarketElementExceptions>(new MarketElementExceptions(badField)));
			}
		}

		MarketElementExceptionsArray::~MarketElementExceptionsArray()
		{
			this->_exceptions.clear();
		}

		Name MarketElementExceptionsArray::name() const
		{
			return Name("exceptions");
		}

		size_t MarketElementExceptionsArray::numValues() const
		{
			return this->_exceptions.size();
		}

		size_t MarketElementExceptionsArray::numElements() const
		{
			return 0;
		}

		SchemaElementDefinition MarketElementExceptionsArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("SubscriptionException"));
			return result;
		}

		bool MarketElementExceptionsArray::isNull() const
		{
			return false;
		}

		bool MarketElementExceptionsArray::isArray() const
		{
			return true;
		}

		bool MarketElementExceptionsArray::isComplexType() const
		{
			return false;
		}

		std::shared_ptr<ElementPtr> MarketElementExceptionsArray::getValueAsElement(int index) const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_exceptions.at(index));
		}

		std::ostream& MarketElementExceptionsArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "exceptions[] = {" << std::endl;

			for(std::vector< std::shared_ptr<MarketElementExceptions> >::const_iterator iter = this->_exceptions.begin(); iter != this->_exceptions.end(); ++iter)
			{
				std::shared_ptr<MarketElementExceptions> elm = *iter;
				elm->print(stream, level, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}