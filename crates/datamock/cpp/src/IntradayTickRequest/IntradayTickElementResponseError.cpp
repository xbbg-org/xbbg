//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickElementResponseError.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickElementResponseError.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "Types/RandomDataGenerator.h"
#include "IntradayTickRequest/IntradayTickElementString.h"
#include "IntradayTickRequest/IntradayTickElementInt.h"
#include "Types/IndentType.h"
#include <algorithm>
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickElementResponseError::IntradayTickElementResponseError() :
			_category(new IntradayTickElementString("category", "BAD_SEC")),
			_subCategory(new IntradayTickElementString("subcategory", "INVALID_SECURITY"))

		{
			int code = RandomDataGenerator::RandomInt(99);
			std::string sourceGibberish = RandomDataGenerator::RandomString(5);
			std::transform(sourceGibberish.begin(), sourceGibberish.end(), sourceGibberish.begin(), ::tolower);

			//source
			std::stringstream sourceValue;
			sourceValue << code << "::" << sourceGibberish.substr(0, sourceGibberish.length() - 2) << RandomDataGenerator::RandomInt(99);
			this->_source = std::shared_ptr<IntradayTickElementString>(new IntradayTickElementString("source", sourceValue.str()));

			//code
			this->_code = std::shared_ptr<IntradayTickElementInt>(new IntradayTickElementInt("code", code));

			//message
			std::stringstream messageValue;
			messageValue << "Unknown/Invalid security [nid:" << code << "]";
			this->_message = std::shared_ptr<IntradayTickElementString>(new IntradayTickElementString("message", messageValue.str()));
		}

		IntradayTickElementResponseError::~IntradayTickElementResponseError()
		{
		}

		Name IntradayTickElementResponseError::name() const
		{
			Name result("responseError");
			return result;
		}

		const char* IntradayTickElementResponseError::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		int IntradayTickElementResponseError::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		SchemaElementDefinition IntradayTickElementResponseError::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ErrorInfo"));
			return result;
		}

		std::shared_ptr<ElementPtr> IntradayTickElementResponseError::getElement(const char* name) const
		{
			if(strncmp("source", name, 7) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_source);

			else if(strncmp("code", name, 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_code);

			else if(strncmp("category", name, 9) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_category);

			else if(strncmp("message", name, 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_message);

			else if(strncmp("subcategory", name, 12) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_subCategory);

			else
				throw elementPtrEx;
		}

		bool IntradayTickElementResponseError::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp("source", name, 7) == 0) ||
				(strncmp("code", name, 5) == 0) ||
				(strncmp("category", name, 9) == 0) ||
				(strncmp("message", name, 8) == 0) ||
				(strncmp("subcategory", name, 12) == 0);
		}

		std::ostream& IntradayTickElementResponseError::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);

			stream << tabs << "responseError = {" << std::endl;
			this->_source->print(stream, level + 1, spacesPerLevel);
			this->_code->print(stream, level + 1, spacesPerLevel);
			this->_category->print(stream, level + 1, spacesPerLevel);
			this->_message->print(stream, level + 1, spacesPerLevel);
			this->_subCategory->print(stream, level + 1, spacesPerLevel);
			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}