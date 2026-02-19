//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketElementExceptions.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"

namespace BEmu
{
	namespace MarketDataRequest
	{
		class MarketElementString;
		class MarketElementReason;

		class MarketElementExceptions : public ElementPtr
		{
			private:
				std::shared_ptr<MarketElementString> _fieldId;
				std::shared_ptr<MarketElementReason> _reason;

			public:
				using ElementPtr::getElement;

				MarketElementExceptions(const std::string& badField);
				~MarketElementExceptions();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
				virtual SchemaElementDefinition elementDefinition() const;
		
				virtual bool isNull() const;
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual const char* getElementAsString(const char* name) const;
				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}