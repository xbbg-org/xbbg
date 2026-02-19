//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementSecurityError.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementSecurityError.h"
#include "Types/RandomDataGenerator.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"

#include "ReferenceDataRequest/ReferenceElementString.h"
#include "ReferenceDataRequest/ReferenceElementInt.h"
#include <algorithm>
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementSecurityError::ReferenceElementSecurityError(const std::string& security) :
			_category(new ReferenceElementString("category", "BAD_SEC")),
			_subCategory(new ReferenceElementString("subcategory", "INVALID_SECURITY"))
		{
			int code = RandomDataGenerator::RandomInt(99);

			std::string sourceGibberish = RandomDataGenerator::RandomString(6);
			std::transform(sourceGibberish.begin(), sourceGibberish.end(), sourceGibberish.begin(), ::tolower);

			std::stringstream ssSource;
			ssSource << RandomDataGenerator::RandomInt(999) << "::" << sourceGibberish.substr(0, sourceGibberish.length() - 2) << RandomDataGenerator::RandomInt(99);

			this->_source = std::shared_ptr<ReferenceElementString>(new ReferenceElementString("source", ssSource.str()));

			this->_code = std::shared_ptr<ReferenceElementInt>(new ReferenceElementInt("code", code));

			std::stringstream ssMsg;
			ssMsg << "Unknown/Invalid security [nid:" << code << ']';
			this->_message = std::shared_ptr<ReferenceElementString>(new ReferenceElementString("message", ssMsg.str()));
		}

		ReferenceElementSecurityError::~ReferenceElementSecurityError()
		{
		}

		Name ReferenceElementSecurityError::name() const { return Name("securityError"); }
		size_t ReferenceElementSecurityError::numValues() const { return 1; }
		size_t ReferenceElementSecurityError::numElements() const { return 5; }

		bool ReferenceElementSecurityError::isNull() const { return false; }
		bool ReferenceElementSecurityError::isArray() const { return false; }
		bool ReferenceElementSecurityError::isComplexType() const { return true; }

		SchemaElementDefinition ReferenceElementSecurityError::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ErrorInfo"));
			return result;
		}

		const char* ReferenceElementSecurityError::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		int ReferenceElementSecurityError::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		std::shared_ptr<ElementPtr> ReferenceElementSecurityError::getElement(const char* name) const
		{
			if(strncmp(name, "category", 9) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_category);

			else if(strncmp(name, "code", 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_code);

			else if(strncmp(name, "message", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_message);

			else if(strncmp(name, "source", 7) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_source);

			else if(strncmp(name, "subcategory", 12) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_subCategory);

			else
				throw elementPtrEx;
		}

		bool ReferenceElementSecurityError::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp(name, "category", 9) == 0) ||
				(strncmp(name, "code", 5) == 0) ||
				(strncmp(name, "message", 8) == 0) ||
				(strncmp(name, "source", 7) == 0) ||
				(strncmp(name, "subcategory", 12) == 0);
		}

		std::ostream& ReferenceElementSecurityError::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldData = {" << std::endl;
			
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