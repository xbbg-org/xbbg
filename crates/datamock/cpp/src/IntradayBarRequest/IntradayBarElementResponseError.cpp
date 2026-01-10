//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarElementResponseError.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include "IntradayBarRequest/IntradayBarElementString.h"
#include "IntradayBarRequest/IntradayBarElementInt.h"
#include "IntradayBarRequest/IntradayBarElementResponseError.h"
#include "Types/RandomDataGenerator.h"
#include "Types/IndentType.h"
#include <algorithm>
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarElementResponseError::IntradayBarElementResponseError(const std::string& security) :
			_category(new IntradayBarElementString("category", "BAD_SEC")),
			_subCategory(new IntradayBarElementString("subcategory", "INVALID_SECURITY"))
		{
			int code = RandomDataGenerator::RandomInt(99);
			std::string sourceGibberish = RandomDataGenerator::RandomString(5);
			std::transform(sourceGibberish.begin(), sourceGibberish.end(), sourceGibberish.begin(), ::tolower);

			//source
			std::stringstream sourceValue;
			sourceValue << code << "::" << sourceGibberish.substr(0, sourceGibberish.length() - 2) << RandomDataGenerator::RandomInt(99);
			this->_source = std::shared_ptr<IntradayBarElementString>(new IntradayBarElementString("source", sourceValue.str()));

			//code
			this->_code = std::shared_ptr<IntradayBarElementInt>(new IntradayBarElementInt("code", code));

			//message
			std::stringstream messageValue;
			messageValue << "Unknown/Invalid security [nid:" << code << "]";
			this->_message = std::shared_ptr<IntradayBarElementString>(new IntradayBarElementString("message", messageValue.str()));
		}

		IntradayBarElementResponseError::~IntradayBarElementResponseError()
		{
		}

		Name IntradayBarElementResponseError::name() const
		{
			Name result("responseError");
			return result;
		}

		size_t IntradayBarElementResponseError::numValues() const
		{
			return 1;
		}

		size_t IntradayBarElementResponseError::numElements() const
		{
			return 5;
		}

		SchemaElementDefinition IntradayBarElementResponseError::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ErrorInfo"));
			return result;
		}

		bool IntradayBarElementResponseError::isArray() const
		{
			return false;
		}

		bool IntradayBarElementResponseError::isComplexType() const
		{
			return false;
		}

		int IntradayBarElementResponseError::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		const char* IntradayBarElementResponseError::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::shared_ptr<ElementPtr> IntradayBarElementResponseError::getElement(const char* name) const
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

		bool IntradayBarElementResponseError::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp("source", name, 7) == 0) ||
				(strncmp("code", name, 5) == 0) ||
				(strncmp("category", name, 9) == 0) ||
				(strncmp("message", name, 8) == 0) ||
				(strncmp("subcategory", name, 12) == 0);
		}

		std::ostream& IntradayBarElementResponseError::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

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