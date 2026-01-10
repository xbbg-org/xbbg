//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarElementTickData.h" company="Jordan Robinson">
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

	namespace IntradayBarRequest
	{
		class IntradayBarTickDataType;
		class IntradayBarElementDateTime;
		class IntradayBarElementDouble;
		class IntradayBarElementLong;
		class IntradayBarElementInt;

		class IntradayBarElementTickData : public ElementPtr
		{
			private:
				std::shared_ptr<IntradayBarElementDateTime> _time;
				std::shared_ptr<IntradayBarElementDouble> _open, _high, _low, _close, _value;
				std::shared_ptr<IntradayBarElementLong> _volume;
				std::shared_ptr<IntradayBarElementInt> _numEvents;

			public:
				using ElementPtr::getElement;

				IntradayBarElementTickData(const IntradayBarTickDataType& arg);
				~IntradayBarElementTickData();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;
				
				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;
				
				virtual int getElementAsInt32(const char* name) const;
				virtual long getElementAsInt64(const char* name) const;
				virtual Datetime getElementAsDatetime(const char* name) const;
				virtual double getElementAsFloat64(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}