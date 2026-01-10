//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequest.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequest.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/RequestPtr.h"
#include "BloombergTypes/Datetime.h"
#include "Types/RandomDataGenerator.h"
#include "IntradayTickRequest/IntradayTickRequestElementStringArray.h"
#include <cstring>
#include <vector>
#include <ostream>
#include <iostream>

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequest::IntradayTickRequest(const Service& svc) :
			_eventTypes(new IntradayTickRequestElementStringArray("eventTypes"))
		{
			this->_service = svc;
			this->_requestType = RequestPtr::intradayTick;
		}

		IntradayTickRequest::~IntradayTickRequest()
		{
		}

		const Service IntradayTickRequest::getService() const
		{
			return this->_service;
		}

		bool IntradayTickRequest::hasStartDate() const
		{
			return this->_timeStart != nullptr;
		}

		bool IntradayTickRequest::hasEndDate() const
		{
			return this->_timeEnd != 0;
		}

		const Datetime IntradayTickRequest::getStartDate() const
		{
			Datetime dtStartOrYesterday;
			if(this->_timeStart == 0)
			{
				dtStartOrYesterday = Datetime::Today();
				dtStartOrYesterday.addDays(-1); //yesterday
			}
			else
			{
				dtStartOrYesterday = this->_timeStart->getDate();
			}

			// Note: Real Bloomberg caps at 140 days, but for mock testing we allow any date
			return dtStartOrYesterday;
		}

		const Datetime IntradayTickRequest::getEndDate() const
		{
			Datetime dtEnd;
			if(this->_timeEnd == 0)
				dtEnd = Datetime::Now(); //right now
			else
				dtEnd = this->_timeEnd->getDate();

			return dtEnd;
		}

		std::vector<Datetime> IntradayTickRequest::getDates() const
		{
			std::vector<Datetime> result;

			Datetime dtStart = this->getStartDate();
			Datetime dtEnd = this->getEndDate();
			Datetime dtLoop = dtStart;

			while(dtLoop < dtEnd)
			{
				result.push_back(dtLoop);
				dtLoop.addMinutes(RandomDataGenerator::IntradayTickIntervalInMinutes());
			}

			return result;
		}

		bool IntradayTickRequest::includeConditionCodes() const
		{
			if (this->_includeConditionCodes == nullptr)
				return false;
			return this->_includeConditionCodes->getBool();
		}

		std::string IntradayTickRequest::security() const
		{
			return this->_security->security();
		}

		Datetime IntradayTickRequest::dtStart() const
		{
			return this->_timeStart->getDate();
		}

		Datetime IntradayTickRequest::dtEnd() const
		{
			return this->_timeEnd->getDate();
		}

		Element IntradayTickRequest::getElement(const char* name)
		{
			if(strncmp(name, "eventTypes", 11) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_eventTypes) );
				return result;
			}

			else if(strncmp(name, "security", 9) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_security) );
				return result;
			}

			else if(strncmp(name, "startDateTime", 14) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_timeStart) );
				return result;
			}

			else if(strncmp(name, "endDateTime", 12) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_timeEnd) );
				return result;
			}
			
			else if(strncmp(name, "includeConditionCodes", 22) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_includeConditionCodes) );
				return result;
			}
			
			else if(strncmp(name, "includeNonPlottableEvents", 26) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_includeNonPlottableEvents) );
				return result;
			}

			else if(strncmp(name, "includeExchangeCodes", 21) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_includeExchangeCodes) );
				return result;
			}

			else if(strncmp(name, "returnEids", 11) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_returnEids) );
				return result;
			}

			else if(strncmp(name, "includeBrokerCodes", 19) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_includeBrokerCodes) );
				return result;
			}

			else if(strncmp(name, "includeRpsCodes", 16) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_includeRpsCodes) );
				return result;
			}

			else if(strncmp(name, "includeBicMicCodes", 19) == 0)
			{
				Element result( std::dynamic_pointer_cast<ElementPtr>(this->_includeBicMicCodes) );
				return result;
			}

			else
				throw requestEx;
		}

		void IntradayTickRequest::append(const char* name, const char* value)
		{
			if(strncmp(name, "eventTypes", 11) == 0)
				this->_eventTypes->addValue(value);

			else
				throw requestEx;
		}

		void IntradayTickRequest::set(const char* name, const char* value)
		{
			if(strncmp(name, "security", 9) == 0)
				this->_security = std::shared_ptr<IntradayTickRequestElementString>(new IntradayTickRequestElementString(std::string(name), value));

			else
				throw requestEx;
		}

		void IntradayTickRequest::set(const char* name, const Datetime& value)
		{
			if(strncmp(name, "startDateTime", 14) == 0)
				this->_timeStart = std::shared_ptr<IntradayTickRequestElementTime>(new IntradayTickRequestElementTime(std::string(name), value));
			else if(strncmp(name, "endDateTime", 12) == 0)
				this->_timeEnd = std::shared_ptr<IntradayTickRequestElementTime>(new IntradayTickRequestElementTime(std::string(name), value));
			else
				throw requestEx;
		}

		void IntradayTickRequest::set(const char* name, bool value)
		{
			if(strncmp(name, "includeConditionCodes", 22) == 0)
				this->_includeConditionCodes = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));
			
			else if(strncmp(name, "includeNonPlottableEvents", 26) == 0)
				this->_includeNonPlottableEvents = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));

			else if(strncmp(name, "includeExchangeCodes", 21) == 0)
				this->_includeExchangeCodes = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));

			else if(strncmp(name, "returnEids", 11) == 0)
				this->_returnEids = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));

			else if(strncmp(name, "includeBrokerCodes", 19) == 0)
				this->_includeBrokerCodes = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));

			else if(strncmp(name, "includeRpsCodes", 16) == 0)
				this->_includeRpsCodes = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));

			else if(strncmp(name, "includeBicMicCodes", 19) == 0)
				this->_includeBicMicCodes = std::shared_ptr<IntradayTickRequestElementBool>(new IntradayTickRequestElementBool(std::string(name), value));

			else
				throw requestEx;
		}

		std::ostream& IntradayTickRequest::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "IntradayTickRequest = {" << std::endl;

			if(this->_security != 0)
				this->_security->print(stream, level + 1, spacesPerLevel);
			
			if(this->_eventTypes != 0)
				this->_eventTypes->print(stream, level + 1, spacesPerLevel);
			
			if(this->_timeStart != 0)
				this->_timeStart->print(stream, level + 1, spacesPerLevel);
			
			if(this->_timeEnd != 0)
				this->_timeEnd->print(stream, level + 1, spacesPerLevel);
			
			if(this->_includeConditionCodes != 0)
				this->_includeConditionCodes->print(stream, level + 1, spacesPerLevel);
			
			if(this->_includeNonPlottableEvents != 0)
				this->_includeNonPlottableEvents->print(stream, level + 1, spacesPerLevel);
			
			if(this->_includeExchangeCodes != 0)
				this->_includeExchangeCodes->print(stream, level + 1, spacesPerLevel);
			
			if(this->_returnEids != 0)
				this->_returnEids->print(stream, level + 1, spacesPerLevel);
			
			if(this->_includeBrokerCodes != 0)
				this->_includeBrokerCodes->print(stream, level + 1, spacesPerLevel);
			
			if(this->_includeRpsCodes != 0)
				this->_includeRpsCodes->print(stream, level + 1, spacesPerLevel);
			
			if(this->_includeBicMicCodes != 0)
				this->_includeBicMicCodes->print(stream, level + 1, spacesPerLevel);

			stream << "}" << std::endl;
			return stream;
		}

	}
}