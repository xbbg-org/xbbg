//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementSecurityError.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementSecurityError.h"
#include "HistoricalDataRequest/HistoricElementString.h"
#include "HistoricalDataRequest/HistoricElementInt.h"

#include "Types/RandomDataGenerator.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include <algorithm>
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementSecurityError::HistoricElementSecurityError(const std::string& security) :
			_category(new HistoricElementString("category", "BAD_SEC")),
			_subCategory(new HistoricElementString("subcategory", "INVALID_SECURITY")),
			_code(new HistoricElementInt("code", RandomDataGenerator::RandomInt(99)))
		{
			int nid = RandomDataGenerator::RandomInt(99);

			std::string sourceGibberish = RandomDataGenerator::RandomString(5);
			std::transform(sourceGibberish.begin(), sourceGibberish.end(), sourceGibberish.begin(), ::tolower);

			//source
			std::stringstream sourceValue;
			sourceValue << nid << "::" << sourceGibberish.substr(0, sourceGibberish.length() - 2) << RandomDataGenerator::RandomInt(99);
			this->_source = std::shared_ptr<HistoricElementString>(new HistoricElementString("source", sourceValue.str()));

			//message
			std::stringstream messageValue;
			messageValue << "Unknown/Invalid security [nid:" << nid << "]";
			this->_message = std::shared_ptr<HistoricElementString>(new HistoricElementString("message", messageValue.str()));
		}

		HistoricElementSecurityError::~HistoricElementSecurityError()
		{
		}


		Name HistoricElementSecurityError::name() const
		{
			Name result("securityError");
			return result;
		}

		size_t HistoricElementSecurityError::numValues() const
		{
			return 1;
		}

		size_t HistoricElementSecurityError::numElements() const
		{
			return 5;
		}

		SchemaElementDefinition HistoricElementSecurityError::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ErrorInfo"));
			return result;
		}

		
		bool HistoricElementSecurityError::isNull() const
		{
			return false;
		}

		bool HistoricElementSecurityError::isArray() const
		{
			return false;
		}

		bool HistoricElementSecurityError::isComplexType() const
		{
			return true;
		}


		std::shared_ptr<ElementPtr> HistoricElementSecurityError::getElement(const char* name) const
		{
			if(strncmp(name, "source", 7) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_source);

			else if(strncmp(name, "code", 5) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_code);

			else if(strncmp(name, "category", 9) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_category);

			else if(strncmp(name, "message", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_message);

			else if(strncmp(name, "subcategory", 12) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_subCategory);

			else
				throw elementPtrEx;
		}

		bool HistoricElementSecurityError::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp(name, "source", 7) == 0) ||
				(strncmp(name, "code", 5) == 0) ||
				(strncmp(name, "category", 9) == 0) ||
				(strncmp(name, "message", 8) == 0) ||
				(strncmp(name, "subcategory", 12) == 0);
		}


		int HistoricElementSecurityError::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		const char* HistoricElementSecurityError::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}


		std::ostream& HistoricElementSecurityError::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldData = {" << std::endl;
			
			this->_source->print(stream, level, spacesPerLevel);
			this->_code->print(stream, level, spacesPerLevel);
			this->_category->print(stream, level, spacesPerLevel);
			this->_message->print(stream, level, spacesPerLevel);
			this->_subCategory->print(stream, level, spacesPerLevel);

			stream << tabs << '}' << std::endl;
			
			return stream;
		}

	}
}