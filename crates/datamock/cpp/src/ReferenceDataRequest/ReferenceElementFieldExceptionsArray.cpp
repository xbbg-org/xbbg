//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementFieldExceptionsArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementFieldExceptionsArray.h"
#include "ReferenceDataRequest/ReferenceElementFieldExceptions.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementFieldExceptionsArray::ReferenceElementFieldExceptionsArray(const std::vector<std::string>& badFields)
		{
			for(std::vector<std::string>::const_iterator iter = badFields.begin(); iter != badFields.end(); ++iter)
			{
				std::string str = *iter;				
				std::shared_ptr<ReferenceElementFieldExceptions> elmP(new ReferenceElementFieldExceptions(str));

				this->_exceptions.push_back(elmP);
			}
		}

		ReferenceElementFieldExceptionsArray::~ReferenceElementFieldExceptionsArray()
		{
			this->_exceptions.clear();
		}

		Name ReferenceElementFieldExceptionsArray::name() const { return Name("fieldExceptions"); }
		size_t ReferenceElementFieldExceptionsArray::numValues() const { return this->_exceptions.size(); }
		size_t ReferenceElementFieldExceptionsArray::numElements() const { return 0; }

		SchemaElementDefinition ReferenceElementFieldExceptionsArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("FieldException"));
			return result;
		}

		bool ReferenceElementFieldExceptionsArray::isNull() const { return false; }
		bool ReferenceElementFieldExceptionsArray::isArray() const { return true; }
		bool ReferenceElementFieldExceptionsArray::isComplexType() const { return false; }

		std::shared_ptr<ElementPtr> ReferenceElementFieldExceptionsArray::getValueAsElement(int index) const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_exceptions[index]);
		}

		std::ostream& ReferenceElementFieldExceptionsArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level + 1, spacesPerLevel));

			stream << tabs << "fieldExceptions[] = {" << std::endl;
			
			for(std::vector< std::shared_ptr<ReferenceElementFieldExceptions> >::const_iterator iter = this->_exceptions.begin(); iter != this->_exceptions.end(); ++iter)
			{
				std::shared_ptr<ReferenceElementFieldExceptions> elm = *iter;
				elm->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}