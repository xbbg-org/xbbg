//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceRequestElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceRequestElement.h"
#include "ReferenceDataRequest/ReferenceRequest.h"
#include "ReferenceDataRequest/ReferenceRequestElementStringArray.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceRequestElement::ReferenceRequestElement(const ReferenceRequest& request)
			: _request(request)
		{
		}

		ReferenceRequestElement::~ReferenceRequestElement()
		{
		}

		Name ReferenceRequestElement::name() const
		{
			Name result("ReferenceDataRequest");
			return result;
		}

		size_t ReferenceRequestElement::numElements() const
		{
			return 2; // securities and fields
		}

		bool ReferenceRequestElement::hasElement(const char* name, bool excludeNullElements) const
		{
			(void)excludeNullElements;
			if (strncmp(name, "securities", 11) == 0) return true;
			if (strncmp(name, "fields", 7) == 0) return true;
			return false;
		}

		std::shared_ptr<ElementPtr> ReferenceRequestElement::getElement(const char* name) const
		{
			// Check cache first
			auto it = _cachedElements.find(name);
			if (it != _cachedElements.end()) {
				return it->second;
			}

			std::shared_ptr<ElementPtr> result;

			if (strncmp(name, "securities", 11) == 0) {
				auto elem = std::make_shared<ReferenceRequestElementStringArray>("securities");
				for (const auto& sec : _request.getSecurities()) {
					elem->appendValue(sec.c_str());
				}
				result = elem;
			}
			else if (strncmp(name, "fields", 7) == 0) {
				auto elem = std::make_shared<ReferenceRequestElementStringArray>("fields");
				for (const auto& field : _request.getFields()) {
					elem->appendValue(field.c_str());
				}
				result = elem;
			}
			else {
				throw elementPtrEx;
			}

			// Cache the result
			_cachedElements[name] = result;
			return result;
		}

		std::shared_ptr<ElementPtr> ReferenceRequestElement::getElement(int position) const
		{
			switch (position) {
				case 0: return getElement("securities");
				case 1: return getElement("fields");
			}
			throw elementPtrEx;
		}

		std::ostream& ReferenceRequestElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			_request.print(stream, level, spacesPerLevel);
			return stream;
		}
	}
}
