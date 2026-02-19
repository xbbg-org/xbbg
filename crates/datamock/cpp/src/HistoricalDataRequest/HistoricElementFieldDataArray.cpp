//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementFieldDataArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementFieldDataArray.h"
#include "HistoricalDataRequest/HistoricElementFieldData.h"
#include "Types/ObjectType.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementFieldDataArray::HistoricElementFieldDataArray(const std::map<Datetime, std::map<std::string, ObjectType>>& fieldData)
		{
			for(std::map<Datetime, std::map<std::string, ObjectType>>::const_iterator iter = fieldData.begin(); iter != fieldData.end(); ++iter)
			{
				std::map<std::string, ObjectType> mm(iter->second);
				std::shared_ptr<HistoricElementFieldData> elmFieldDataP(new HistoricElementFieldData(iter->first, mm));

				this->_fieldData.push_back(elmFieldDataP);
			}
		}

		HistoricElementFieldDataArray::~HistoricElementFieldDataArray()
		{
			this->_fieldData.clear();
		}


		std::shared_ptr<ElementPtr> HistoricElementFieldDataArray::getValueAsElement(int index) const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_fieldData.at(index));
		}


		Name HistoricElementFieldDataArray::name() const
		{
			Name result("fieldData");
			return result;
		}

		size_t HistoricElementFieldDataArray::numValues() const
		{
			return this->_fieldData.size();
		}

		size_t HistoricElementFieldDataArray::numElements() const
		{
			return 0;
		}

		SchemaElementDefinition HistoricElementFieldDataArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("HistoricalDataRow"));
			return result;
		}

		
		bool HistoricElementFieldDataArray::isNull() const
		{
			return false;
		}

		bool HistoricElementFieldDataArray::isArray() const
		{
			return true;
		}

		bool HistoricElementFieldDataArray::isComplexType() const
		{
			return false;
		}


		std::ostream& HistoricElementFieldDataArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldData[] = {" << std::endl;
			for(std::vector< std::shared_ptr<HistoricElementFieldData> >::const_iterator iter = this->_fieldData.begin(); iter != this->_fieldData.end(); ++iter)
			{
				std::shared_ptr<HistoricElementFieldData> elm = *iter;
				elm->print(stream, level + 1, spacesPerLevel);
			}
			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}