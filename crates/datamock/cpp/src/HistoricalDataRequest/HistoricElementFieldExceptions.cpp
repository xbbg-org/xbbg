//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementFieldExceptions.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementFieldExceptions.h"
#include "HistoricalDataRequest/HistoricElementString.h"
#include "HistoricalDataRequest/HistoricElementErrorInfo.h"

#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementFieldExceptions::HistoricElementFieldExceptions(const std::string& badField) :
			_fieldId(new HistoricElementString("fieldId", badField)),
			_errorInfo(new HistoricElementErrorInfo())
		{
		}

		HistoricElementFieldExceptions::~HistoricElementFieldExceptions()
		{
		}


		Name HistoricElementFieldExceptions::name() const
		{
			Name result("fieldExceptions");
			return result;
		}

		size_t HistoricElementFieldExceptions::numValues() const
		{
			return 1;
		}

		size_t HistoricElementFieldExceptions::numElements() const
		{
			return 2;
		}

		SchemaElementDefinition HistoricElementFieldExceptions::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("FieldException"));
			return result;
		}

		
		bool HistoricElementFieldExceptions::isNull() const
		{
			return false;
		}

		bool HistoricElementFieldExceptions::isArray() const
		{
			return false;
		}

		bool HistoricElementFieldExceptions::isComplexType() const
		{
			return true;
		}


		std::shared_ptr<ElementPtr> HistoricElementFieldExceptions::getElement(const char* name) const
		{
			if(strncmp(name, "errorInfo", 10) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_errorInfo);

			else if(strncmp(name, "fieldId", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_fieldId);

			else
				throw elementPtrEx;
		}

		bool HistoricElementFieldExceptions::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				(strncmp(name, "errorInfo", 10) == 0) ||
				(strncmp(name, "fieldId", 8) == 0);
		}

		int HistoricElementFieldExceptions::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		const char* HistoricElementFieldExceptions::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}


		std::ostream& HistoricElementFieldExceptions::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldExceptions = {" << std::endl;
			
			this->_fieldId->print(stream, level + 1, spacesPerLevel);
			this->_errorInfo->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}