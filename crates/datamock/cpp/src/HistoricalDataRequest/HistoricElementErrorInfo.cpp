//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementErrorInfo.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "Types/RandomDataGenerator.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/SchemaElementDefinition.h"
#include "HistoricalDataRequest/HistoricElementErrorInfo.h"
#include "HistoricalDataRequest/HistoricElementString.h"
#include "HistoricalDataRequest/HistoricElementInt.h"
#include <algorithm>
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementErrorInfo::HistoricElementErrorInfo() : 
			_category(std::shared_ptr<HistoricElementString>(new HistoricElementString("category", "BAD_FLD"))),
			_message(std::shared_ptr<HistoricElementString>(new HistoricElementString("message", "Invalid field"))), 
			_subCategory(std::shared_ptr<HistoricElementString>(new HistoricElementString("subcategory", "NOT_APPLICABLE_TO_HIST_DATA")))
		{
			std::string sourceGibberish = RandomDataGenerator::RandomString(5);
			std::transform(sourceGibberish.begin(), sourceGibberish.end(), sourceGibberish.begin(), ::tolower);

			std::stringstream ssSource;
			ssSource << RandomDataGenerator::RandomInt(999) << "::" << sourceGibberish.substr(0, sourceGibberish.length() - 2) << RandomDataGenerator::RandomInt(99);


			this->_source = std::shared_ptr<HistoricElementString>(new HistoricElementString("source", ssSource.str()));
			this->_code = std::shared_ptr<HistoricElementInt>(new HistoricElementInt("code", RandomDataGenerator::RandomInt(99)));
		}

		HistoricElementErrorInfo::~HistoricElementErrorInfo()
		{
		}

		Name HistoricElementErrorInfo::name() const
		{
			Name result("errorInfo");
			return result;
		}

		size_t HistoricElementErrorInfo::numValues() const
		{
			return 1;
		}

		size_t HistoricElementErrorInfo::numElements() const
		{
			return 5;
		}

		SchemaElementDefinition HistoricElementErrorInfo::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ErrorInfo"));
			return result;
		}

		bool HistoricElementErrorInfo::isNull() const
		{
			return false;
		}

		bool HistoricElementErrorInfo::isArray() const
		{
			return false;
		}

		bool HistoricElementErrorInfo::isComplexType() const
		{
			return true;
		}

		std::shared_ptr<ElementPtr> HistoricElementErrorInfo::getElement(const char* name) const
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

		bool HistoricElementErrorInfo::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp(name, "category", 9) == 0) ||
				(strncmp(name, "code", 5) == 0) ||
				(strncmp(name, "message", 8) == 0) ||
				(strncmp(name, "source", 7) == 0) ||
				(strncmp(name, "subcategory", 12) == 0);
		}


		int HistoricElementErrorInfo::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		const char* HistoricElementErrorInfo::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::ostream& HistoricElementErrorInfo::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs = IndentType::Indent(level, spacesPerLevel);

			stream << tabs << "errorInfo = {" << std::endl;
			
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