//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayBarRequest/IntradayBarRequest.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayBarRequest/IntradayBarRequest.h"
#include "IntradayBarRequest/IntradayBarRequestElement.h"
#include "IntradayBarRequest/IntradayBarRequestElementInt.h"
#include "IntradayBarRequest/IntradayBarRequestElementBool.h"
#include "IntradayBarRequest/IntradayBarRequestElementTime.h"
#include "IntradayBarRequest/IntradayBarRequestElementString.h"
#include "IntradayBarRequest/IntradayBarRequestElementStringArray.h"

#include "BloombergTypes/Service.h"
#include "BloombergTypes/Element.h"
#include <cstring>
#include <ostream>


namespace BEmu
{
	namespace IntradayBarRequest
	{
		IntradayBarRequest::IntradayBarRequest(const Service& svc)
		{
			this->_isNull_eventTypes = true;
			this->_isNull_security = true;
			this->_isNull_dtStart = true;
			this->_isNull_dtEnd = true;
			this->_isNull_intervalInMinutes = true;
			this->_isNull_gapFillInitialBar = true;
			this->_isNull_returnEids = true;
			this->_isNull_adjustmentNormalElement = true;
			this->_isNull_adjustmentAbnormalElement = true;
			this->_isNull_adjustmentSplitElement = true;
			this->_isNull_adjustmentFollowDPDF = true;

			this->_service = svc;
			this->_requestType = RequestPtr::intradayBar;
		}

		IntradayBarRequest::~IntradayBarRequest()
		{
		}

		std::vector<Datetime> IntradayBarRequest::getDateTimes() const
		{
			//dtStart, dtEnd, and interval are required
			if(this->_isNull_dtStart || this->_isNull_dtEnd || this->_isNull_intervalInMinutes)
				throw requestEx;

			int intervalInMinutes = this->_intervalInMinutes->getInt();
			if (intervalInMinutes < 1 || intervalInMinutes > 1440) //if less than one, the loop below will never terminate
				throw requestEx;
			
			Datetime dtStart = this->_dtStart->getDatetime();
			Datetime dtEnd = this->_dtEnd->getDatetime();

			if(dtStart >= dtEnd) //dtStart must be before dtEnd
				throw requestEx;

			std::vector<Datetime> result;

			Datetime dtLoop(dtStart.year(), dtStart.month(), dtStart.day(), dtStart.hours(), dtStart.minutes(), dtStart.seconds());
			while(dtLoop < dtEnd)
			{
				result.push_back(Datetime(dtLoop));
				dtLoop.addMinutes(this->_intervalInMinutes->getInt());
			}

			return result;
		}

		bool IntradayBarRequest::hasStartDate() const
		{
			return !this->_isNull_dtStart;
		}

		bool IntradayBarRequest::hasEndDate() const
		{
			return !this->_isNull_dtEnd;
		}

		Datetime IntradayBarRequest::getDtStart() const
		{
			return this->_dtStart->getDatetime();
		}

		Datetime IntradayBarRequest::getDtEnd() const
		{
			return this->_dtEnd->getDatetime();
		}

		const Service IntradayBarRequest::getService() const
		{
			return this->_service;
		}

		const std::string& IntradayBarRequest::security() const
		{
			return this->_security->security();
		}

		void IntradayBarRequest::set(const char* name, const char* value)
		{
			if(strncmp(name, "security", 9) == 0)
			{
				this->_security = std::shared_ptr<IntradayBarRequestElementString>(new IntradayBarRequestElementString(name, value, true));
				this->_isNull_security = false;
			}
			else if(strncmp(name, "eventType", 10) == 0)
			{
				this->_eventTypes = std::shared_ptr<IntradayBarRequestElementString>(new IntradayBarRequestElementString(name, value, false));
				this->_isNull_eventTypes = false; //only one eventType allowed per request
			}
			else
				throw requestEx;
		}

		void IntradayBarRequest::set(const char* name, const Datetime& elementValue)
		{
			if(strncmp(name, "startDateTime", 14) == 0)
			{
				this->_dtStart = std::shared_ptr<IntradayBarRequestElementTime>(new IntradayBarRequestElementTime(name, elementValue));
				this->_isNull_dtStart = false;
			}
			else if(strncmp(name, "endDateTime", 12) == 0)
			{
				this->_dtEnd = std::shared_ptr<IntradayBarRequestElementTime>(new IntradayBarRequestElementTime(name, elementValue));
				this->_isNull_dtEnd = false;
			}
			else
				throw requestEx;
		}

		void IntradayBarRequest::set(const char* name, int elementValue)
		{
			if(strncmp(name, "interval", 9) == 0)
			{
				this->_intervalInMinutes = std::shared_ptr<IntradayBarRequestElementInt>(new IntradayBarRequestElementInt(name, elementValue));
				this->_isNull_intervalInMinutes = false;
			}
			else
				throw requestEx;
		}

		void IntradayBarRequest::set(const char* name, bool elementValue)
		{
			if(strncmp(name, "gapFillInitialBar", 18) == 0)
			{
				this->_gapFillInitialBar = std::shared_ptr<IntradayBarRequestElementBool>(new IntradayBarRequestElementBool(name, elementValue));
				this->_isNull_gapFillInitialBar = false;
			}
			else if(strncmp(name, "returnEids", 11) == 0)
			{
				this->_returnEids = std::shared_ptr<IntradayBarRequestElementBool>(new IntradayBarRequestElementBool(name, elementValue));
				this->_isNull_returnEids = false;
			}
			else if(strncmp(name, "adjustmentNormal", 17) == 0)
			{
				this->_adjustmentNormalElement = std::shared_ptr<IntradayBarRequestElementBool>(new IntradayBarRequestElementBool(name, elementValue));
				this->_isNull_adjustmentNormalElement = false;
			}
			else if(strncmp(name, "adjustmentAbnormal", 19) == 0)
			{
				this->_adjustmentAbnormalElement = std::shared_ptr<IntradayBarRequestElementBool>(new IntradayBarRequestElementBool(name, elementValue));
				this->_isNull_adjustmentAbnormalElement = false;
			}
			else if(strncmp(name, "adjustmentSplit", 16) == 0)
			{
				this->_adjustmentSplitElement = std::shared_ptr<IntradayBarRequestElementBool>(new IntradayBarRequestElementBool(name, elementValue));
				this->_isNull_adjustmentSplitElement = false;
			}
			else if(strncmp(name, "adjustmentFollowDPDF", 21) == 0)
			{
				this->_adjustmentFollowDPDF = std::shared_ptr<IntradayBarRequestElementBool>(new IntradayBarRequestElementBool(name, elementValue));
				this->_isNull_adjustmentFollowDPDF = false;
			}
			else
				throw requestEx;
		}

		std::ostream& IntradayBarRequest::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "IntradayBarRequest = {" << std::endl;
			
			if(!this->_isNull_security)
				this->_security->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_eventTypes)
				this->_eventTypes->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_dtEnd)
				this->_dtEnd->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_dtStart)
				this->_dtStart->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_intervalInMinutes)
				this->_intervalInMinutes->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_gapFillInitialBar)
				this->_gapFillInitialBar->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_returnEids)
				this->_returnEids->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentNormalElement)
				this->_adjustmentNormalElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentAbnormalElement)
				this->_adjustmentAbnormalElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentSplitElement)
				this->_adjustmentSplitElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentFollowDPDF)
				this->_adjustmentFollowDPDF->print(stream, level + 1, spacesPerLevel);
			
			stream << '}' << std::endl;
			return stream;
		}

		Element IntradayBarRequest::asElement()
		{
			std::shared_ptr<IntradayBarRequestElement> elem(new IntradayBarRequestElement(*this));
			return Element(std::dynamic_pointer_cast<ElementPtr>(elem));
		}

	}
}