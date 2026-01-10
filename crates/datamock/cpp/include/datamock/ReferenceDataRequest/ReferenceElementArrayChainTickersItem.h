//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceElementArrayChainTickersItem.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include "ReferenceDataRequest/ReferenceElementArrayChainTickers.h"

namespace BEmu
{
	class Name;
	class Datetime;

	namespace ReferenceDataRequest
	{
		class ReferenceElementString;

		class ReferenceElementArrayChainTickersItem : public ElementPtr
		{
			private:
				std::shared_ptr<ReferenceElementString> _element;

			public:
				using ElementPtr::getElement;

				ReferenceElementArrayChainTickersItem(const std::string& ticker, const Datetime& dtExp, ReferenceDataRequest::OptionalityEnum::EnumType optionality, int strike);
				~ReferenceElementArrayChainTickersItem();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isNull() const;
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual const char* getElementAsString(const char* name) const;
				
				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}