//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickRequest.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <vector>
#include "BloombergTypes/Service.h"
#include "BloombergTypes/RequestPtr.h"

#include "IntradayTickRequest/IntradayTickRequestElementString.h"
#include "IntradayTickRequest/IntradayTickRequestElementStringArray.h"
#include "IntradayTickRequest/IntradayTickRequestElementTime.h"
#include "IntradayTickRequest/IntradayTickRequestElementBool.h"

namespace BEmu
{
	class Datetime;
	class Element;

	namespace IntradayTickRequest
	{
		class IntradayTickRequest : public RequestPtr
		{
			private:
				std::shared_ptr<IntradayTickRequestElementString> _security;
				std::shared_ptr<IntradayTickRequestElementStringArray> _eventTypes;
				std::shared_ptr<IntradayTickRequestElementTime> _timeStart, _timeEnd;
				std::shared_ptr<IntradayTickRequestElementBool> _includeConditionCodes, _includeNonPlottableEvents, _includeExchangeCodes, _returnEids,
					_includeBrokerCodes, _includeRpsCodes, _includeBicMicCodes;

				Service _service;
				
				const Datetime getStartDate() const; //used only as a helper for getDates()
				const Datetime getEndDate() const; //used only as a helper for getDates()

			public:
				using RequestPtr::set;

				IntradayTickRequest(const Service& svc);
				~IntradayTickRequest();
				const Service getService() const;
				std::vector<Datetime> getDates() const;
				bool includeConditionCodes() const;
				std::string security() const;
				bool hasStartDate() const;
				bool hasEndDate() const;

				Datetime dtStart() const;
				Datetime dtEnd() const;

				virtual Element getElement(const char* name);
				virtual void append(const char* name, const char* value);
				virtual void set(const char* name, const char* value);
				virtual void set(const char* name, const Datetime& value);
				virtual void set(const char* name, bool value);

				virtual std::ostream& print(std::ostream& stream, int level, int spacesPerLevel) const;
		};
	}
}