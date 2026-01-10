//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceElement.h" company="Jordan Robinson">
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
	class Name;

	namespace ReferenceDataRequest
	{
		class ReferenceMessage;
		class ReferenceElementSecurityDataArray;

		class ReferenceElement : public ElementPtr
		{
			private:
				std::shared_ptr<ReferenceElementSecurityDataArray> _securities;

			public:
				using ElementPtr::getElement;

				ReferenceElement(const ReferenceMessage& arg);
				~ReferenceElement();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isNull() const;
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}