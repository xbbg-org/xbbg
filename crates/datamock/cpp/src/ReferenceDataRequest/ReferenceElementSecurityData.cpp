//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementSecurityData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementSecurityData.h"
#include "ReferenceDataRequest/ReferenceElementFieldExceptionsArray.h"
#include "ReferenceDataRequest/ReferenceElementString.h"

#include "ReferenceDataRequest/ReferenceElementInt.h"
#include "ReferenceDataRequest/ReferenceElementSecurityError.h"
#include "ReferenceDataRequest/ReferenceElementFieldData.h"

#include "Types/Rules.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementSecurityData::ReferenceElementSecurityData(const std::string& securityName, std::map<std::string, ObjectType> * fieldData, int sequenceNumber) :
			_elmSecurityName(new ReferenceElementString("security", securityName))
		{
			this->_isSecurityError = Rules::IsSecurityError(securityName);

			{ //find bad field names
				std::vector<std::string> badFields;

				for(std::map<std::string, ObjectType>::const_iterator iter = fieldData->begin(); iter != fieldData->end(); ++iter)
				{
					std::string str = iter->first;
					ObjectType obj = iter->second;

					if(Rules::IsBadField(str))
						badFields.push_back(str);
				}

				//remove bad field names from the dictionary
				for(std::vector<std::string>::const_iterator iter = badFields.begin(); iter != badFields.end(); ++iter)
				{
					std::string badField = *iter;
					fieldData->erase(badField);
				}

                if (badFields.size() == 0)
				{
                    this->_elmFieldExceptions = std::shared_ptr<ReferenceElementFieldExceptionsArray>();
					this->_isNull_elmFieldExceptions = true;
				}
                else
				{
                    this->_elmFieldExceptions = std::shared_ptr<ReferenceElementFieldExceptionsArray>(new ReferenceElementFieldExceptionsArray(badFields));
					this->_isNull_elmFieldExceptions = false;
				}
			}

            if (this->_isSecurityError)
            {
				this->_elmSequenceNumber = std::shared_ptr<ReferenceElementInt>(new ReferenceElementInt("sequenceNumber", sequenceNumber));
				this->_elmSecError = std::shared_ptr<ReferenceElementSecurityError>(new ReferenceElementSecurityError(securityName));

				std::map<std::string, ObjectType> mm;

				this->_elmFieldData = std::shared_ptr<ReferenceElementFieldData>(new ReferenceElementFieldData(&mm));
            }
            else
            {
				this->_elmSequenceNumber = std::shared_ptr<ReferenceElementInt>(new ReferenceElementInt("sequenceNumber", sequenceNumber));
				this->_elmSecError = std::shared_ptr<ReferenceElementSecurityError>();
				this->_elmFieldData = std::shared_ptr<ReferenceElementFieldData>(new ReferenceElementFieldData(fieldData));
            }
		}

		ReferenceElementSecurityData::~ReferenceElementSecurityData()
		{
		}

		Name ReferenceElementSecurityData::name() const { return Name("securityData"); }
		size_t ReferenceElementSecurityData::numValues() const { return 0; }
		
		size_t ReferenceElementSecurityData::numElements() const { return 4 + (this->_isNull_elmFieldExceptions ? 0 : 1); }

		SchemaElementDefinition ReferenceElementSecurityData::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("ReferenceSecurityData"));
			return result;
		}

		const char* ReferenceElementSecurityData::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::shared_ptr<ElementPtr> ReferenceElementSecurityData::getElement(const char* name) const
		{
			if(strncmp(name, "security", 9) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmSecurityName);

			else if(strncmp(name, "sequenceNumber", 15) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmSequenceNumber);

			else if(strncmp(name, "fieldData", 10) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmFieldData);

			else if(!this->_isNull_elmFieldExceptions && strncmp(name, "fieldExceptions", 16) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmFieldExceptions);

			else if(this->_isSecurityError && strncmp(name, "securityError", 14) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_elmSecError);

			else throw elementPtrEx;
		}

		bool ReferenceElementSecurityData::hasElement(const char* name, bool excludeNullElements) const
		{
			return 
				(strncmp(name, "security", 9) == 0) ||
				(strncmp(name, "sequenceNumber", 15) == 0) ||
				(strncmp(name, "fieldData", 10) == 0) ||
				(!this->_isNull_elmFieldExceptions && strncmp(name, "fieldExceptions", 16) == 0) ||				
				(this->_isSecurityError && strncmp(name, "securityError", 14) == 0);
		}

		std::ostream& ReferenceElementSecurityData::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "securityData = {" << std::endl;

			this->_elmSecurityName->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_elmFieldExceptions)
				this->_elmFieldExceptions->print(stream, level + 1, spacesPerLevel);

			this->_elmSequenceNumber->print(stream, level + 1, spacesPerLevel);
			
            if (this->_isSecurityError)
				this->_elmSecError->print(stream, level + 1, spacesPerLevel);
            else
				this->_elmFieldData->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}