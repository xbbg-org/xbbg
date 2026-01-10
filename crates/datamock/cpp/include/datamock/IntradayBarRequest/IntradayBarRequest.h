//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayBarRequest/IntradayBarRequest.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Service.h"
#include "BloombergTypes/RequestPtr.h"
#include <vector>

namespace BEmu
{
	class Datetime;

	namespace IntradayBarRequest
	{
		class IntradayBarRequestElementString;
		class IntradayBarRequestElementStringArray;
		class IntradayBarRequestElementTime;
		class IntradayBarRequestElementInt;
		class IntradayBarRequestElementBool;

		class IntradayBarRequest : public RequestPtr
		{
			private:
				Service _service;

				std::shared_ptr<IntradayBarRequestElementString> _security;
				std::shared_ptr<IntradayBarRequestElementString> _eventTypes;
				std::shared_ptr<IntradayBarRequestElementTime> _dtStart, _dtEnd;
				std::shared_ptr<IntradayBarRequestElementInt> _intervalInMinutes;
				std::shared_ptr<IntradayBarRequestElementBool> _gapFillInitialBar, _returnEids, _adjustmentNormalElement, _adjustmentAbnormalElement, _adjustmentSplitElement, _adjustmentFollowDPDF;

				bool _isNull_security;
				bool _isNull_eventTypes;
				bool _isNull_dtStart, _isNull_dtEnd;
				bool _isNull_intervalInMinutes;
				bool _isNull_gapFillInitialBar, _isNull_returnEids, _isNull_adjustmentNormalElement, _isNull_adjustmentAbnormalElement, _isNull_adjustmentSplitElement, _isNull_adjustmentFollowDPDF;

			public:
				IntradayBarRequest(const Service& svc);
				~IntradayBarRequest();
				const Service getService() const;
				std::vector<Datetime> getDateTimes() const;
				const std::string& security() const;
				
				Datetime getDtStart() const;
				Datetime getDtEnd() const;
				bool hasStartDate() const;
				bool hasEndDate() const;

				virtual void set(const char* name, const char* value);
				virtual void set(const char* name, const Datetime& value);
				virtual void set(const char* name, int value);
				virtual void set(const char* name, bool value);

				virtual Element asElement();

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}