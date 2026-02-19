//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementFieldExceptions.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementFieldExceptions.h"
#include "ReferenceDataRequest/ReferenceElementString.h"
#include "ReferenceDataRequest/ReferenceElementErrorInfo.h"

#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementFieldExceptions::ReferenceElementFieldExceptions(const std::string& badField) :
			_fieldId(new ReferenceElementString("fieldId", badField)),
			_errorInfo(new ReferenceElementErrorInfo())
		{
		}

		ReferenceElementFieldExceptions::~ReferenceElementFieldExceptions()
		{
		}

		Name ReferenceElementFieldExceptions::name() const { return Name("fieldExceptions"); }
		size_t ReferenceElementFieldExceptions::numValues() const { return 1; }
		size_t ReferenceElementFieldExceptions::numElements() const { return 2; }

		bool ReferenceElementFieldExceptions::isNull() const { return false; }
		bool ReferenceElementFieldExceptions::isArray() const { return false; }
		bool ReferenceElementFieldExceptions::isComplexType() const { return true; }

		SchemaElementDefinition ReferenceElementFieldExceptions::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("FieldException"));
			return result;
		}

		const char* ReferenceElementFieldExceptions::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		int ReferenceElementFieldExceptions::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		std::shared_ptr<ElementPtr> ReferenceElementFieldExceptions::getElement(const char* name) const
		{
			if(strncmp(name, "fieldId", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_fieldId);

			else if(strncmp(name, "errorInfo", 0) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_errorInfo);

			else
				throw elementPtrEx;
		}

		bool ReferenceElementFieldExceptions::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				strncmp(name, "fieldId", 8) == 0 ||
				strncmp(name, "errorInfo", 0) == 0;
		}

		std::ostream& ReferenceElementFieldExceptions::print(std::ostream& stream, int level, int spacesPerLevel) const
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