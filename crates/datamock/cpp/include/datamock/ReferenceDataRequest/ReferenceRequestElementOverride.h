//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceRequestElementOverride.h" company="Jordan Robinson">
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
	namespace ReferenceDataRequest
	{
		class ReferenceElementString;
		class ReferenceElementObject;

		class ReferenceRequestElementOverride : public ElementPtr
		{
			private:
				std::shared_ptr<ReferenceElementString> _fieldId;
				std::shared_ptr<ReferenceElementObject> _value;

			public:
				using ElementPtr::getElement;

				ReferenceRequestElementOverride();
				~ReferenceRequestElementOverride();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;

				virtual void setElement(const char* name, const char* value);
				virtual void setElement(const char* name, int value);

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}