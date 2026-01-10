//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequestElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarRequestElement.h"
#include "IntradayBarRequest/IntradayBarRequest.h"
#include "IntradayBarRequest/IntradayBarRequestElementString.h"
#include "IntradayBarRequest/IntradayBarRequestElementTime.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequestElement::IntradayBarRequestElement(const IntradayBarRequest& request)
			: _request(request)
		{
		}

		IntradayBarRequestElement::~IntradayBarRequestElement()
		{
		}

		Name IntradayBarRequestElement::name() const
		{
			Name result("IntradayBarRequest");
			return result;
		}

		size_t IntradayBarRequestElement::numElements() const
		{
			size_t count = 1; // security is always present
			if (_request.hasStartDate()) count++;
			if (_request.hasEndDate()) count++;
			return count;
		}

		bool IntradayBarRequestElement::hasElement(const char* name, bool excludeNullElements) const
		{
			(void)excludeNullElements;
			if (strncmp(name, "security", 9) == 0) return true;
			if (strncmp(name, "startDateTime", 14) == 0) return _request.hasStartDate();
			if (strncmp(name, "endDateTime", 12) == 0) return _request.hasEndDate();
			return false;
		}

		std::shared_ptr<ElementPtr> IntradayBarRequestElement::getElement(const char* name) const
		{
			// Check cache first
			auto it = _cachedElements.find(name);
			if (it != _cachedElements.end()) {
				return it->second;
			}

			std::shared_ptr<ElementPtr> result;

			if (strncmp(name, "security", 9) == 0) {
				result = std::make_shared<IntradayBarRequestElementString>("security", _request.security(), false);
			}
			else if (strncmp(name, "startDateTime", 14) == 0 && _request.hasStartDate()) {
				result = std::make_shared<IntradayBarRequestElementTime>("startDateTime", _request.getDtStart());
			}
			else if (strncmp(name, "endDateTime", 12) == 0 && _request.hasEndDate()) {
				result = std::make_shared<IntradayBarRequestElementTime>("endDateTime", _request.getDtEnd());
			}
			else {
				throw elementPtrEx;
			}

			// Cache the result
			_cachedElements[name] = result;
			return result;
		}

		std::shared_ptr<ElementPtr> IntradayBarRequestElement::getElement(int position) const
		{
			switch (position) {
				case 0: return getElement("security");
				case 1: if (_request.hasStartDate()) return getElement("startDateTime"); break;
				case 2: if (_request.hasEndDate()) return getElement("endDateTime"); break;
			}
			throw elementPtrEx;
		}

		std::ostream& IntradayBarRequestElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			_request.print(stream, level, spacesPerLevel);
			return stream;
		}
	}
}
