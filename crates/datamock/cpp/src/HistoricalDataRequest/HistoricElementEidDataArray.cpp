//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementEidDataArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementEidDataArray.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include "Types/RandomDataGenerator.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementEidDataArray::HistoricElementEidDataArray()
		{
			// Generate 2-4 random entitlement IDs (typical Bloomberg response has 2-3)
			int numEids = RandomDataGenerator::RandomInt(2, 4);
			for (int i = 0; i < numEids; i++)
			{
				// Real Bloomberg EIDs are typically 5-digit numbers like 14003, 14080
				int eid = RandomDataGenerator::RandomInt(10000, 19999);
				_eids.push_back(eid);
			}
		}

		HistoricElementEidDataArray::~HistoricElementEidDataArray()
		{
		}

		Name HistoricElementEidDataArray::name() const
		{
			Name result("eidData");
			return result;
		}

		size_t HistoricElementEidDataArray::numValues() const
		{
			return _eids.size();
		}

		SchemaElementDefinition HistoricElementEidDataArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("eidData"));
			return result;
		}

		int HistoricElementEidDataArray::getValueAsInt32(int index) const
		{
			if (index >= 0 && (size_t)index < _eids.size())
				return _eids[index];
			throw elementPtrEx;
		}

		std::ostream& HistoricElementEidDataArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));
			stream << tabs << "eidData[] = {" << std::endl;
			
			std::string innerTabs(IndentType::Indent(level + 1, spacesPerLevel));
			for (size_t i = 0; i < _eids.size(); i++)
			{
				stream << innerTabs << _eids[i];
				if (i < _eids.size() - 1)
					stream << ",";
				stream << std::endl;
			}
			
			stream << tabs << "}" << std::endl;
			return stream;
		}
	}
}
