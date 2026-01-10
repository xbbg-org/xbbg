//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementFieldExceptionsArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementFieldExceptionsArray.h"
#include "HistoricalDataRequest/HistoricElementFieldExceptions.h"

#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementFieldExceptionsArray::HistoricElementFieldExceptionsArray(const std::vector<std::string>& badFields)
		{
			for(std::vector<std::string>::const_iterator iter = badFields.begin(); iter != badFields.end(); ++iter)
			{
				std::string str = *iter;				
				std::shared_ptr<HistoricElementFieldExceptions> elmP(new HistoricElementFieldExceptions(str));
				
				this->_exceptions.push_back(elmP);
			}
		}

		HistoricElementFieldExceptionsArray::~HistoricElementFieldExceptionsArray()
		{
			this->_exceptions.clear();
		}


		Name HistoricElementFieldExceptionsArray::name() const
		{
			Name result("fieldExceptions");
			return result;
		}

		size_t HistoricElementFieldExceptionsArray::numValues() const
		{
			return this->_exceptions.size();
		}

		size_t HistoricElementFieldExceptionsArray::numElements() const
		{
			return 0;
		}

		SchemaElementDefinition HistoricElementFieldExceptionsArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("FieldException"));
			return result;
		}

		
		bool HistoricElementFieldExceptionsArray::isNull() const
		{
			return false;
		}

		bool HistoricElementFieldExceptionsArray::isArray() const
		{
			return true;
		}

		bool HistoricElementFieldExceptionsArray::isComplexType() const
		{
			return false;
		}


		std::shared_ptr<ElementPtr> HistoricElementFieldExceptionsArray::getValueAsElement(int index) const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_exceptions.at(index));
		}


		std::ostream& HistoricElementFieldExceptionsArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldExceptions = {" << std::endl;

			for(std::vector< std::shared_ptr<HistoricElementFieldExceptions> >::const_iterator iter = this->_exceptions.begin(); iter != this->_exceptions.end(); ++iter)
			{
				std::shared_ptr<HistoricElementFieldExceptions> elm = *iter;
				elm->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}