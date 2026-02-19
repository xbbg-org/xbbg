//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricElementFieldDataArray.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include <vector>
#include <map>

namespace BEmu
{
	class ObjectType;

	namespace HistoricalDataRequest
	{
		class HistoricElementFieldData;

		class HistoricElementFieldDataArray : public ElementPtr
		{
			private:
				std::vector< std::shared_ptr<HistoricElementFieldData> > _fieldData;

			public:
				HistoricElementFieldDataArray(const std::map<Datetime, std::map<std::string, ObjectType>>& fieldData);
				~HistoricElementFieldDataArray();

				virtual std::shared_ptr<ElementPtr> getValueAsElement(int index) const;

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isNull() const;
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}