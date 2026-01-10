//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElementSecurityData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElementSecurityData.h"
#include "HistoricalDataRequest/HistoricElementFieldExceptionsArray.h"
#include "HistoricalDataRequest/HistoricElementString.h"
#include "HistoricalDataRequest/HistoricElementInt.h"
#include "HistoricalDataRequest/HistoricElementSecurityError.h"
#include "HistoricalDataRequest/HistoricElementFieldDataArray.h"
#include "HistoricalDataRequest/HistoricElementEidDataArray.h"

#include "Types/Rules.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElementSecurityData::HistoricElementSecurityData(
			const std::string& securityName, 
			const std::vector<std::string>& badFields, 
			const std::map<Datetime, std::map<std::string, ObjectType>>& fieldData,
			int sequenceNumber) :
				_elmSecurityName(new HistoricElementString("security", securityName)),
				_elmSequenceNumber(new HistoricElementInt("sequenceNumber", sequenceNumber)),
				_elmEidData(new HistoricElementEidDataArray())
		{
			this->_isSecurityError = Rules::IsSecurityError(securityName);
			
            //remove bad field names from the dictionary			
            if (badFields.size() == 0)
			{
				this->_elmFieldExceptions = std::shared_ptr<HistoricElementFieldExceptionsArray>();
				this->_isNull_elmFieldExceptions = true;
			}
            else
			{
				this->_elmFieldExceptions = std::shared_ptr<HistoricElementFieldExceptionsArray>(new HistoricElementFieldExceptionsArray(badFields));
				this->_isNull_elmFieldExceptions = false;
			}

			if (this->_isSecurityError)
            {
				this->_elmSecError = std::shared_ptr<HistoricElementSecurityError>(new HistoricElementSecurityError(securityName));
				this->_elmFieldDataArray = std::shared_ptr<HistoricElementFieldDataArray>();
            }
            else
            {
				this->_elmSecError = std::shared_ptr<HistoricElementSecurityError>();
				this->_elmFieldDataArray = std::shared_ptr<HistoricElementFieldDataArray>(new HistoricElementFieldDataArray(fieldData));
            }
		}

		HistoricElementSecurityData::~HistoricElementSecurityData()
		{
		}


		Name HistoricElementSecurityData::name() const
		{
			Name result("securityData");
			return result;
		}

		size_t HistoricElementSecurityData::numValues() const
		{
			return 1;
		}

		size_t HistoricElementSecurityData::numElements() const
		{
			return 4 + (this->_isNull_elmFieldExceptions ? 0 : 1);  // +1 for eidData
		}

		SchemaElementDefinition HistoricElementSecurityData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("HistoricalDataTable"));
			return result;
		}

		
		bool HistoricElementSecurityData::isNull() const
		{
			return false;
		}

		bool HistoricElementSecurityData::isArray() const
		{
			return false;
		}

		bool HistoricElementSecurityData::isComplexType() const
		{
			return true;
		}


		std::shared_ptr<ElementPtr> HistoricElementSecurityData::getElement(const char* name) const
		{
			if(strncmp(name, "fieldData", 10) == 0)
			{
				if(!this->_isSecurityError)
					return std::dynamic_pointer_cast<ElementPtr>(this->_elmFieldDataArray);
			}

			else if(strncmp(name, "security", 9) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmSecurityName);

			else if(strncmp(name, "sequenceNumber", 15) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmSequenceNumber);

			else if(strncmp(name, "eidData", 8) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmEidData);

			else if(strncmp(name, "fieldExceptions", 16) == 0)
			{
				if(this->_elmFieldExceptions != 0)
					return std::dynamic_pointer_cast<ElementPtr>(this->_elmFieldExceptions);
			}

			else if(strncmp(name, "securityError", 14) == 0)
			{
				if(this->_isSecurityError)
					return std::dynamic_pointer_cast<ElementPtr>(this->_elmSecError);
			}

			throw elementPtrEx;
		}

		bool HistoricElementSecurityData::hasElement(const char* name, bool excludeNullElements) const
		{
			return
				( strncmp(name, "fieldData", 10) == 0 && !this->_isSecurityError ) ||
				( strncmp(name, "security", 9) == 0) ||
				( strncmp(name, "sequenceNumber", 15) == 0) ||
				( strncmp(name, "eidData", 8) == 0) ||
				( strncmp(name, "fieldExceptions", 16) == 0 && this->_elmFieldExceptions != 0) ||
				( strncmp(name, "securityError", 14) == 0 && this->_isSecurityError );
		}


		int HistoricElementSecurityData::getElementAsInt32(const char* name) const
		{
			return this->getElement(name)->getValueAsInt32(0);
		}

		const char* HistoricElementSecurityData::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}


		std::ostream& HistoricElementSecurityData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));
			stream << tabs << "securityData = {" << std::endl;
			
			this->_elmSecurityName->print(stream, level + 1, spacesPerLevel);
			this->_elmEidData->print(stream, level + 1, spacesPerLevel);
			this->_elmSequenceNumber->print(stream, level + 1, spacesPerLevel);

			if(this->_elmFieldExceptions != 0)
				this->_elmFieldExceptions->print(stream, level + 1, spacesPerLevel);

			if(this->_isSecurityError)
				this->_elmSecError->print(stream, level + 1, spacesPerLevel);
			else
				this->_elmFieldDataArray->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;

            return stream;
		}

	}
}