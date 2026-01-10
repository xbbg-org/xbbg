//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickElementResponseError.h" company="Jordan Robinson">
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

	namespace IntradayTickRequest
	{
		class IntradayTickElementString;
		class IntradayTickElementInt;

		class IntradayTickElementResponseError : public ElementPtr
		{
			private:
				std::shared_ptr<IntradayTickElementString> _source, _category, _message, _subCategory;
				std::shared_ptr<IntradayTickElementInt> _code;

			public:
				using ElementPtr::getElement;

				IntradayTickElementResponseError();
				~IntradayTickElementResponseError();

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const { return 5; }		
				virtual bool isArray() const { return false; }
				virtual bool isComplexType() const { return true; }
				virtual SchemaElementDefinition elementDefinition() const;
				
				virtual const char* getElementAsString(const char* name) const;
				virtual int getElementAsInt32(const char* name) const;
				
				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}