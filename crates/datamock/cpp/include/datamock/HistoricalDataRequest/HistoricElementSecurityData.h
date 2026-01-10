//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricElementSecurityData.h" company="Jordan Robinson">
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
		class HistoricElementString;
		class HistoricElementFieldDataArray;
		class HistoricElementInt;
		class HistoricElementFieldExceptionsArray;
		class HistoricElementSecurityError;

		class HistoricElementEidDataArray;

		class HistoricElementSecurityData : public ElementPtr
		{
			private:
				std::shared_ptr<HistoricElementString> _elmSecurityName;
				std::shared_ptr<HistoricElementFieldDataArray> _elmFieldDataArray;
				std::shared_ptr<HistoricElementInt> _elmSequenceNumber;
				std::shared_ptr<HistoricElementFieldExceptionsArray> _elmFieldExceptions;
				std::shared_ptr<HistoricElementSecurityError> _elmSecError;
				std::shared_ptr<HistoricElementEidDataArray> _elmEidData;

				bool _isSecurityError;
				bool _isNull_elmFieldExceptions;

			public:
				using ElementPtr::getElement;

				HistoricElementSecurityData(
					const std::string& securityName, 
					const std::vector<std::string>& badFields, 
					const std::map<Datetime, std::map<std::string, ObjectType>>& fieldData, 
					int sequenceNumber);

				~HistoricElementSecurityData();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isNull() const;
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual int getElementAsInt32(const char* name) const;
				virtual const char* getElementAsString(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}