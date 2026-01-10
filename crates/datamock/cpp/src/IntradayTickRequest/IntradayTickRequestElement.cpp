//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequestElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequestElement.h"
#include "IntradayTickRequest/IntradayTickRequest.h"
#include "IntradayTickRequest/IntradayTickRequestElementString.h"
#include "IntradayTickRequest/IntradayTickRequestElementTime.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequestElement::IntradayTickRequestElement(const IntradayTickRequest& request)
			: _request(request)
		{
		}

		IntradayTickRequestElement::~IntradayTickRequestElement()
		{
		}

		Name IntradayTickRequestElement::name() const
		{
			Name result("IntradayTickRequest");
			return result;
		}

		size_t IntradayTickRequestElement::numElements() const
		{
			size_t count = 1; // security is always present
			if (_request.hasStartDate()) count++;
			if (_request.hasEndDate()) count++;
			return count;
		}

		bool IntradayTickRequestElement::hasElement(const char* name, bool excludeNullElements) const
		{
			(void)excludeNullElements;
			if (strncmp(name, "security", 9) == 0) return true;
			if (strncmp(name, "startDateTime", 14) == 0) return _request.hasStartDate();
			if (strncmp(name, "endDateTime", 12) == 0) return _request.hasEndDate();
			return false;
		}

		std::shared_ptr<ElementPtr> IntradayTickRequestElement::getElement(const char* name) const
		{
			// Check cache first
			auto it = _cachedElements.find(name);
			if (it != _cachedElements.end()) {
				return it->second;
			}

			std::shared_ptr<ElementPtr> result;

			if (strncmp(name, "security", 9) == 0) {
				result = std::make_shared<IntradayTickRequestElementString>("security", _request.security());
			}
			else if (strncmp(name, "startDateTime", 14) == 0 && _request.hasStartDate()) {
				result = std::make_shared<IntradayTickRequestElementTime>("startDateTime", _request.dtStart());
			}
			else if (strncmp(name, "endDateTime", 12) == 0 && _request.hasEndDate()) {
				result = std::make_shared<IntradayTickRequestElementTime>("endDateTime", _request.dtEnd());
			}
			else {
				throw elementPtrEx;
			}

			// Cache the result
			_cachedElements[name] = result;
			return result;
		}

		std::shared_ptr<ElementPtr> IntradayTickRequestElement::getElement(int position) const
		{
			switch (position) {
				case 0: return getElement("security");
				case 1: if (_request.hasStartDate()) return getElement("startDateTime"); break;
				case 2: if (_request.hasEndDate()) return getElement("endDateTime"); break;
			}
			throw elementPtrEx;
		}

		std::ostream& IntradayTickRequestElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			_request.print(stream, level, spacesPerLevel);
			return stream;
		}
	}
}
