//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceRequestElementOverrideArray.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/ElementPtr.h"
#include <vector>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		class ReferenceRequestElementOverride;

		class ReferenceRequestElementOverrideArray : public ElementPtr
		{
			private:
				std::vector< std::shared_ptr<ReferenceRequestElementOverride> > _overrides;

			public:
				ReferenceRequestElementOverrideArray();
				~ReferenceRequestElementOverrideArray();

				virtual Name name() const;
				virtual size_t numValues() const;
				virtual size_t numElements() const;
		
				virtual bool isNull() const;
				virtual bool isArray() const;
				virtual bool isComplexType() const;

				virtual std::shared_ptr<ElementPtr> getValueAsElement(int index) const;

				virtual std::shared_ptr<ElementPtr> appendElement();

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}