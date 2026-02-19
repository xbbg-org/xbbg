//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarElementResponseError.h" company="Jordan Robinson">
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

	namespace IntradayBarRequest
	{
		class IntradayBarElementString;
		class IntradayBarElementInt;

		class IntradayBarElementResponseError : public ElementPtr
		{
			private:
				std::shared_ptr<IntradayBarElementString> _source, _category, _message, _subCategory;
				std::shared_ptr<IntradayBarElementInt> _code;

			public:
				using ElementPtr::getElement;

				IntradayBarElementResponseError(const std::string& security);
				~IntradayBarElementResponseError();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isArray() const;
				virtual bool isComplexType() const;
								
				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual int getElementAsInt32(const char* name) const;
				virtual const char* getElementAsString(const char* name) const;

				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}