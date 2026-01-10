//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceRequestElement.h" company="Jordan Robinson">
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
	namespace ReferenceDataRequest
	{
		class ReferenceRequest;

		// Element wrapper for ReferenceRequest that exposes request parameters
		class ReferenceRequestElement : public ElementPtr
		{
			private:
				const ReferenceRequest& _request;
				mutable std::map<std::string, std::shared_ptr<ElementPtr>> _cachedElements;

			public:
				ReferenceRequestElement(const ReferenceRequest& request);
				~ReferenceRequestElement();

				virtual Name name() const;
				virtual size_t numValues() const { return 1; }
				virtual size_t numElements() const;
		
				virtual bool isNull() const { return false; }
				virtual bool isArray() const { return false; }
				virtual bool isComplexType() const { return true; }

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;
				virtual std::shared_ptr<ElementPtr> getElement(int position) const;
				virtual bool hasElement(const char* name, bool excludeNullElements = false) const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}
