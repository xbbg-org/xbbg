//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequestElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequestElement.h"
#include "HistoricalDataRequest/HistoricRequest.h"
#include "HistoricalDataRequest/HistoricRequestElementStringArray.h"
#include "HistoricalDataRequest/HistoricRequestElementDate.h"
#include "HistoricalDataRequest/HistoricRequestElementBool.h"
#include "HistoricalDataRequest/HistoricRequestElementInt.h"
#include "HistoricalDataRequest/HistoricRequestElementString.h"
#include "BloombergTypes/Name.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequestElement::HistoricRequestElement(const HistoricRequest& request)
			: _request(request)
		{
		}

		HistoricRequestElement::~HistoricRequestElement()
		{
		}

		Name HistoricRequestElement::name() const
		{
			Name result("HistoricalDataRequest");
			return result;
		}

		size_t HistoricRequestElement::numElements() const
		{
			size_t count = 2; // securities and fields are always present
			if (_request.hasStartDate()) count++;
			if (_request.hasEndDate()) count++;
			return count;
		}

		bool HistoricRequestElement::hasElement(const char* name, bool excludeNullElements) const
		{
			(void)excludeNullElements;
			if (strncmp(name, "securities", 11) == 0) return true;
			if (strncmp(name, "fields", 7) == 0) return true;
			if (strncmp(name, "startDate", 10) == 0) return _request.hasStartDate();
			if (strncmp(name, "endDate", 8) == 0) return _request.hasEndDate();
			return false;
		}

		std::shared_ptr<ElementPtr> HistoricRequestElement::getElement(const char* name) const
		{
			// Check cache first
			auto it = _cachedElements.find(name);
			if (it != _cachedElements.end()) {
				return it->second;
			}

			std::shared_ptr<ElementPtr> result;

			if (strncmp(name, "securities", 11) == 0) {
				auto elem = std::make_shared<HistoricRequestElementStringArray>("securities");
				for (const auto& sec : _request.securities()) {
					elem->appendValue(sec.c_str());
				}
				result = elem;
			}
			else if (strncmp(name, "fields", 7) == 0) {
				auto elem = std::make_shared<HistoricRequestElementStringArray>("fields");
				for (const auto& field : _request.fields()) {
					elem->appendValue(field.c_str());
				}
				result = elem;
			}
			else if (strncmp(name, "startDate", 10) == 0 && _request.hasStartDate()) {
				result = std::make_shared<HistoricRequestElementDate>("startDate", _request.dtStart());
			}
			else if (strncmp(name, "endDate", 8) == 0 && _request.hasEndDate()) {
				result = std::make_shared<HistoricRequestElementDate>("endDate", _request.dtEnd());
			}
			else {
				throw elementPtrEx;
			}

			// Cache the result
			_cachedElements[name] = result;
			return result;
		}

		std::shared_ptr<ElementPtr> HistoricRequestElement::getElement(int position) const
		{
			switch (position) {
				case 0: return getElement("securities");
				case 1: return getElement("fields");
				case 2: if (_request.hasStartDate()) return getElement("startDate"); break;
				case 3: if (_request.hasEndDate()) return getElement("endDate"); break;
			}
			throw elementPtrEx;
		}

		std::ostream& HistoricRequestElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			_request.print(stream, level, spacesPerLevel);
			return stream;
		}
	}
}
