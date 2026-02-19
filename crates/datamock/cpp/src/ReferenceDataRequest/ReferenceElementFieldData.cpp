//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementFieldData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementFieldData.h"
#include "Types/ObjectType.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"

#include "ReferenceDataRequest/ReferenceElementDouble.h"
#include "ReferenceDataRequest/ReferenceElementInt.h"
#include "ReferenceDataRequest/ReferenceElementDateTime.h"
#include "ReferenceDataRequest/ReferenceElementString.h"
#include "ReferenceDataRequest/ReferenceElementArrayChainTickers.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementFieldData::ReferenceElementFieldData(std::map<std::string, ObjectType> * values)
		{
			for(std::map<std::string, ObjectType>::const_iterator iter = values->begin(); iter != values->end(); ++iter)
			{
				std::string name = iter->first;
				ObjectType value = iter->second;

				switch(value.GetType())
				{
					case ObjectType::eDouble:
					{
						std::shared_ptr<ReferenceElementDouble> elmDbl(new ReferenceElementDouble(name, value.ValueAsDouble()));
						std::shared_ptr<ElementPtr> elmDblP(std::dynamic_pointer_cast<ElementPtr>(elmDbl));

						this->_fields.push_back(elmDblP);

						break;
					}
						
					case ObjectType::eInt:
					{
						std::shared_ptr<ReferenceElementInt> elmInt(new ReferenceElementInt(name, value.ValueAsInt()));
						std::shared_ptr<ElementPtr> elmIntP(std::dynamic_pointer_cast<ElementPtr>(elmInt));
						
						this->_fields.push_back(elmIntP);

						break;
					}
						
					case ObjectType::eDatetime:
					{
						std::shared_ptr<ReferenceElementDateTime> elmDt(new ReferenceElementDateTime(name, value.ValueAsDatetime()));
						std::shared_ptr<ElementPtr> elmDtP(std::dynamic_pointer_cast<ElementPtr>(elmDt));
						
						this->_fields.push_back(elmDtP);

						break;
					}
						
					case ObjectType::eString:
					{
						std::shared_ptr<ReferenceElementString> elmStr(new ReferenceElementString(name, value.ValueAsString()));
						std::shared_ptr<ElementPtr> elmStrP(std::dynamic_pointer_cast<ElementPtr>(elmStr));
						
						this->_fields.push_back(elmStrP);

						break;
					}

				case ObjectType::eChainTickers:
					{
						std::shared_ptr<ElementPtr> elmChainP(std::dynamic_pointer_cast<ElementPtr>(value.ValueAsChainTickers()));

						this->_fields.push_back(elmChainP);

						break;
					}
					case ObjectType::eBool:
					case ObjectType::eNothing:
						// Not applicable for reference data fields
						break;
				}
			}
		}

		ReferenceElementFieldData::~ReferenceElementFieldData()
		{
			this->_fields.clear();
		}

		Name ReferenceElementFieldData::name() const { return Name("fieldData"); }
		size_t ReferenceElementFieldData::numValues() const { return 1; }
		size_t ReferenceElementFieldData::numElements() const { return this->_fields.size(); }

		SchemaElementDefinition ReferenceElementFieldData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ReferenceFieldData"));
			return result;
		}

		std::shared_ptr<ElementPtr> ReferenceElementFieldData::getElement(int position) const
		{
			return std::dynamic_pointer_cast<ElementPtr>(this->_fields.at(position));
		}

		std::shared_ptr<ElementPtr> ReferenceElementFieldData::getElement(const char* name) const
		{
			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_fields.begin(); iter != this->_fields.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = *iter;

				if(elm->name() == name)
					return elm;
			}
			throw elementPtrEx;
		}

		bool ReferenceElementFieldData::hasElement(const char* name, bool excludeNullElements) const
		{
			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_fields.begin(); iter != this->_fields.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = *iter;

				if(elm->name() == name)
					return true;
			}
			return false;
		}

		double ReferenceElementFieldData::getElementAsFloat64(const char* name) const
		{
			return this->getElement(name)->getValueAsFloat64(0);
		}

		int ReferenceElementFieldData::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		long ReferenceElementFieldData::getElementAsInt64(const char* name) const
		{
			return this->getElement(name)->getValueAsInt64(0);
		}

		const char* ReferenceElementFieldData::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::ostream& ReferenceElementFieldData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "fieldData = {" << std::endl;
			
			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_fields.begin(); iter != this->_fields.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elmP(*iter);

				elmP->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}