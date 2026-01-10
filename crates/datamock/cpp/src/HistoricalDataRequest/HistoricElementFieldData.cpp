//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementFieldData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementFieldData.h"
#include "HistoricalDataRequest/HistoricElementDateTime.h"
#include "HistoricalDataRequest/HistoricElementDouble.h"

#include "BloombergTypes/Name.h"

#include "Types/ObjectType.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementFieldData::HistoricElementFieldData(const Datetime& date, const std::map<std::string, ObjectType>& values)
		{
			std::shared_ptr<HistoricElementDateTime> elmDate(new HistoricElementDateTime(date));
			std::shared_ptr<ElementPtr> elmDateP(elmDate);

			this->_fields[elmDateP->name().string()] = elmDateP;

			for(std::map<std::string, ObjectType>::const_iterator iter = values.begin(); iter != values.end(); ++iter)
			{
				const std::string str = iter->first;
				const ObjectType obj = iter->second;
				double dvalue;

				if(obj.TryGetDouble(dvalue))
				{
					std::shared_ptr<HistoricElementDouble> elmDouble(new HistoricElementDouble(str, dvalue));
					std::shared_ptr<ElementPtr> elmDoubleP(elmDouble);

					this->_fields[elmDoubleP->name().string()] = elmDoubleP;
				}
			}
		}

		HistoricElementFieldData::~HistoricElementFieldData()
		{
			this->_fields.clear();
		}


		Name HistoricElementFieldData::name() const
		{
			Name result("fieldData");
			return result;
		}

		size_t HistoricElementFieldData::numValues() const
		{
			return 1;
		}

		size_t HistoricElementFieldData::numElements() const
		{
			return this->_fields.size();
		}

		SchemaElementDefinition HistoricElementFieldData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("HistoricalDataRow"));
			return result;
		}

		
		bool HistoricElementFieldData::isNull() const
		{
			return false;
		}

		bool HistoricElementFieldData::isArray() const
		{
			return false;
		}

		bool HistoricElementFieldData::isComplexType() const
		{
			return true;
		}


		bool HistoricElementFieldData::hasElement(const char* name, bool excludeNullElements) const
		{
			return this->_fields.find(name) != this->_fields.end();
		}

		std::shared_ptr<ElementPtr> HistoricElementFieldData::getElement(const char* name) const
		{
			std::string key(name);
			std::map<std::string, std::shared_ptr<ElementPtr> >::const_iterator it = this->_fields.find(key);

			if(it == this->_fields.end())
				throw elementPtrEx;
			else
				return it->second;
		}

		int HistoricElementFieldData::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		Datetime HistoricElementFieldData::getElementAsDatetime(const char* name) const
		{
			return this->getElement(name)->getValueAsDatetime(0);
		}

		const char* HistoricElementFieldData::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		float HistoricElementFieldData::getElementAsFloat32(const char* name) const
		{
			return this->getElement(name)->getValueAsFloat32(0);
		}

		double HistoricElementFieldData::getElementAsFloat64(const char* name) const
		{
			return this->getElement(name)->getValueAsFloat64(0);
		}

		long HistoricElementFieldData::getElementAsInt64(const char* name) const
		{
			return this->getElement(name)->getValueAsInt64(0);
		}


		std::ostream& HistoricElementFieldData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldData = {" << std::endl;
			for(std::map<std::string, std::shared_ptr<ElementPtr> >::const_iterator iter = this->_fields.begin(); iter != this->_fields.end(); ++iter)
			{
				const std::shared_ptr<ElementPtr> elm = iter->second;
				elm->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << std::endl;

			return stream;
		}

	}
}