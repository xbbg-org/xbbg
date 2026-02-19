//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementSecurityDataArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementSecurityDataArray.h"
#include "ReferenceDataRequest/ReferenceElementSecurityData.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementSecurityDataArray::ReferenceElementSecurityDataArray(const std::map<std::string, std::map<std::string, ObjectType>>& securities)
		{
			for(std::map<std::string, std::map<std::string, ObjectType>>::const_iterator iter = securities.begin(); iter != securities.end(); ++iter)
			{
				std::string str = iter->first;
				std::map<std::string, ObjectType> mm = iter->second;

				std::shared_ptr<ReferenceElementSecurityData> refElmSec(new ReferenceElementSecurityData(str, &mm, this->_securities.size()));
				std::shared_ptr<ElementPtr> elm(std::dynamic_pointer_cast<ElementPtr>(refElmSec));

				this->_securities.push_back(elm);
			}
		}

		ReferenceElementSecurityDataArray::ReferenceElementSecurityDataArray(const ReferenceElementSecurityDataArray& arg)
		{
			this->_securities = std::vector< std::shared_ptr<ElementPtr> >(arg._securities);
		}

		ReferenceElementSecurityDataArray::~ReferenceElementSecurityDataArray()
		{
			this->_securities.clear();
		}

		Name ReferenceElementSecurityDataArray::name() const { return Name("securityData"); }
		size_t ReferenceElementSecurityDataArray::numValues() const { return this->_securities.size(); }
		size_t ReferenceElementSecurityDataArray::numElements() const { return 0; }

		SchemaElementDefinition ReferenceElementSecurityDataArray::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ReferenceSecurityData"));
			return result;
		}

		std::shared_ptr<ElementPtr> ReferenceElementSecurityDataArray::getValueAsElement(int index) const
		{
			return this->_securities[index];
		}

		bool ReferenceElementSecurityDataArray::hasElement(const char* name, bool excludeNullElements) const
		{
			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_securities.begin(); iter != this->_securities.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = *iter;

				if(elm->name() == name)
					return true;
			}
			return false;
		}

		std::shared_ptr<ElementPtr> ReferenceElementSecurityDataArray::getElement(const char* name) const
		{
			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_securities.begin(); iter != this->_securities.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = *iter;

				if(elm->name() == name)
					return elm;
			}
			throw elementPtrEx;
		}

		std::ostream& ReferenceElementSecurityDataArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "securityData[] = {" << std::endl;
			
			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_securities.begin(); iter != this->_securities.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = *iter;
				elm->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}
	}
}