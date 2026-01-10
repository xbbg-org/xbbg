//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickElementData.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"

namespace BEmu
{
	class Name;
	class Datetime;

	namespace IntradayTickRequest
	{
		class IntradayTickElementDateTime;
		class IntradayTickElementDouble;
		class IntradayTickElementInt;
		class IntradayTickElementString;
		class IntradayTickElementTuple3;

		class IntradayTickElementData : public ElementPtr
		{
			private:
				bool _includeConditionCodes;
				
				std::shared_ptr<IntradayTickElementDateTime> _time;
				std::shared_ptr<IntradayTickElementDouble> _value;
				std::shared_ptr<IntradayTickElementInt> _size;
				std::shared_ptr<IntradayTickElementString> _type, _conditionCodes;
				
			public:
				IntradayTickElementData(const Datetime& datetime, const IntradayTickElementTuple3& arg, bool includeConditionCodes);
				~IntradayTickElementData();

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 0; }
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isArray() const { return false; }
				virtual bool isComplexType() const { return false; }

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;
				
				virtual std::shared_ptr<ElementPtr> getElement(int position) const;
				
				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual int getElementAsInt32(const char* name) const;
				virtual Datetime getElementAsDatetime(const char* name) const;
				virtual const char* getElementAsString(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}