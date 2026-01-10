//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricRequest.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricRequest.h"
#include "HistoricalDataRequest/HistoricRequestElement.h"
#include "HistoricalDataRequest/HistoricRequestElementDate.h"
#include "HistoricalDataRequest/HistoricRequestElementStringArray.h"
#include "HistoricalDataRequest/HistoricRequestElementInt.h"
#include "HistoricalDataRequest/HistoricRequestElementBool.h"
#include "HistoricalDataRequest/HistoricRequestElementString.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/Element.h"
#include "Types/DisplayFormats.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricRequest::HistoricRequest() :
			_securities(new HistoricRequestElementStringArray("securities")),
			_fields(new HistoricRequestElementStringArray("fields"))
		{
			this->_isNull_securities = false;
			this->_isNull_fields = false;

			this->_isNull_dtStart = true;
			this->_isNull_dtEnd = true;
			this->_isNull_adjustmentNormalElement = true;
			this->_isNull_adjustmentAbnormalElement = true;
			this->_isNull_adjustmentSplitElement = true;
			this->_isNull_maxDataPointElement = true;
			this->_isNull_periodicityAdjustmentElement = true;
			this->_isNull_periodicityElement = true;
			this->_isNull_overrideOptionsElement = true;
			this->_isNull_pricingOptionElement = true;

			this->_periodicityAdjustment = HistDataPeriodicityAdjustmentEnum::actual;
			this->_periodicity = HistDataPeriodicityEnum::daily;
			this->_pricingOption = PricingOptionEnum::price;
			this->_overrideOptions = OverrideOptionsEnum::closingPrice;

			this->_requestType = RequestPtr::historic;
		}

		HistoricRequest::~HistoricRequest()
		{
		}


		std::vector<std::string> HistoricRequest::securities() const
		{
			return this->_securities->values();
		}

		std::vector<std::string> HistoricRequest::fields() const
		{
			return this->_fields->values();
		}

		bool HistoricRequest::hasStartDate() const
		{
			return !this->_isNull_dtStart;
		}

		bool HistoricRequest::hasEndDate() const
		{
			return !this->_isNull_dtEnd;
		}

		Datetime HistoricRequest::dtStart() const
		{
			return this->_dtStart->getDatetime();
		}

		Datetime HistoricRequest::dtEnd() const
		{
			return this->_dtEnd->getDatetime();
		}


		std::vector<Datetime> HistoricRequest::getDates() const
		{
			std::vector<Datetime> dates = this->getDatesBeforeMaxPoints();

			if(this->_isNull_maxDataPointElement)
				return dates;
			else
			{
				int max = this->_maxDataPointElement->getInt();
				int dateCount = dates.size();
				
				std::vector<Datetime> result;
				
				for(int i = 0; i < dateCount; i++, max--)
				{
					Datetime dt = dates.at(i);

					if(max >= 0)
					{
						//skip this date
					}
					else
					{
						result.push_back(dt); //add this date
					}
				}

				return result;
			}
		}

		std::vector<Datetime> HistoricRequest::getDatesBeforeMaxPoints() const
		{
			std::vector<Datetime> result;

			Datetime dtStart; //BEmu.Session.SendRequest assures that dtStart is not null
			if(this->hasStartDate())
				dtStart = this->dtStart();
			else
			{
				dtStart = Datetime::Today();
				dtStart.addYears(-1);
			}

			Datetime dtEnd;
			if(this->hasEndDate())
				dtEnd = this->dtEnd();
			else
			{
				dtEnd = Datetime::Today();
				dtEnd.addDays(-1);
			}

			if(this->_periodicityAdjustment == HistDataPeriodicityAdjustmentEnum::fiscal) //I use the start of the month as the fiscal adjustment.  It's fake.
			{
				int day = (int)dtStart.day();
				dtStart.addDays(-day);
			}

			Datetime dtCurrent = dtStart;
			Datetime dtToday = Datetime::Today();
			do
			{
				result.push_back(dtCurrent);

				switch(this->_periodicity)
				{
					case HistDataPeriodicityEnum::weekly:
						dtCurrent.addDays(7);
						break;
					case HistDataPeriodicityEnum::monthly:
						dtCurrent.addMonths(1);
						break;
					case HistDataPeriodicityEnum::quarterly:
						dtCurrent.addMonths(3);
						break;
					case HistDataPeriodicityEnum::semi_annually:
						dtCurrent.addMonths(6);
						break;
					case HistDataPeriodicityEnum::yearly:
						dtCurrent.addYears(1);
						break;
					case HistDataPeriodicityEnum::daily:
					default:
						dtCurrent.addDays(1);
						break;
				}

				if(dtCurrent.getWeekDay() == Datetime::Saturday)
					dtCurrent.addDays(2);

				else if(dtCurrent.getWeekDay() == Datetime::Sunday)
					dtCurrent.addDays(1);


			} while(dtCurrent <= dtEnd && dtCurrent <= dtToday);

			return result;
		}


		void HistoricRequest::append(const char* name, const char* value)
		{
			if(strncmp(name, "securities", 11) == 0)
				this->_securities->appendValue(value);

			else if(strncmp(name, "fields", 7) == 0)
				this->_fields->appendValue(value);

			else
				throw requestEx;
		}


		void HistoricRequest::set(const char* name, const char* value)
		{
			if(strncmp(name, "startDate", 10) == 0)
			{
				Datetime dt;
				if(DisplayFormats::HistoricalOrReferenceRequests_TryParseInput(value, dt))
				{
					this->_dtStart = std::shared_ptr<HistoricRequestElementDate>(new HistoricRequestElementDate("startDate", dt));
					this->_isNull_dtStart = false;
				}
				else
					throw requestEx;
			}
			else if(strncmp(name, "endDate", 8) == 0)
			{
				Datetime dt;
				if(DisplayFormats::HistoricalOrReferenceRequests_TryParseInput(value, dt))
				{
					this->_dtEnd = std::shared_ptr<HistoricRequestElementDate>(new HistoricRequestElementDate("endDate", dt));
					this->_isNull_dtEnd = false;
				}
				else
					throw requestEx;
				
			}
			else if(strncmp(name, "periodicityAdjustment", 22) == 0)
			{
				if(strncmp(value, "CALENDAR", 9) == 0)
					this->_periodicityAdjustment = HistDataPeriodicityAdjustmentEnum::calendar;
				
				else if(strncmp(value, "FISCAL", 7) == 0)
					this->_periodicityAdjustment = HistDataPeriodicityAdjustmentEnum::fiscal;
				
				else if(strncmp(value, "ACTUAL", 7) == 0)
					this->_periodicityAdjustment = HistDataPeriodicityAdjustmentEnum::actual;

				else
					throw requestEx;

				this->_periodicityAdjustmentElement = std::shared_ptr<HistoricRequestElementString>( new HistoricRequestElementString("periodicityAdjustment", value) );
				this->_isNull_periodicityAdjustmentElement = false;
			}
			else if(strncmp(name, "periodicitySelection", 21) == 0)
			{
				if(strncmp(value, "WEEKLY", 7) == 0)
					this->_periodicity = HistDataPeriodicityEnum::weekly;
				
				else if(strncmp(value, "MONTHLY", 8) == 0)
					this->_periodicity = HistDataPeriodicityEnum::monthly;
				
				else if(strncmp(value, "QUARTERLY", 10) == 0)
					this->_periodicity = HistDataPeriodicityEnum::quarterly;
				
				else if(strncmp(value, "SEMI_ANNUALLY", 14) == 0)
					this->_periodicity = HistDataPeriodicityEnum::semi_annually;
				
				else if(strncmp(value, "YEARLY", 7) == 0)
					this->_periodicity = HistDataPeriodicityEnum::yearly;
				
				else if(strncmp(value, "DAILY", 6) == 0)
					this->_periodicity = HistDataPeriodicityEnum::daily;

				else
					throw requestEx;

				this->_periodicityElement = std::shared_ptr<HistoricRequestElementString>( new HistoricRequestElementString("periodicitySelection", value) );
				this->_isNull_periodicityElement = false;
			}
			else if(strncmp(name, "pricingOption", 14) == 0)
			{
				if(strncmp(value, "PRICING_OPTION_YIELD", 21) == 0)
					this->_pricingOption = PricingOptionEnum::yield;
				
				else if(strncmp(value, "PRICING_OPTION_PRICE", 21) == 0)
					this->_pricingOption = PricingOptionEnum::price;

				else
					throw requestEx;

				this->_pricingOptionElement = std::shared_ptr<HistoricRequestElementString>( new HistoricRequestElementString("pricingOption", value) );
				this->_isNull_pricingOptionElement = false;
			}
			else if(strncmp(name, "overrideOption", 15) == 0)
			{
				if(strncmp(value, "OVERRIDE_OPTION_GPA", 20) == 0)
					this->_overrideOptions = OverrideOptionsEnum::averagePrice;

				else if(strncmp(value, "OVERRIDE_OPTION_CLOSE", 22) == 0)
					this->_overrideOptions = OverrideOptionsEnum::closingPrice;

				else
					throw requestEx;

				this->_overrideOptionsElement = std::shared_ptr<HistoricRequestElementString>( new HistoricRequestElementString("overrideOption", value) );
				this->_isNull_overrideOptionsElement = false;
			}
			else
				throw requestEx;
		}

		void HistoricRequest::set(const char* name, bool value)
		{
			if(strncmp(name, "adjustmentNormal", 17) == 0)
			{
				this->_adjustmentNormalElement = std::shared_ptr<HistoricRequestElementBool>(new HistoricRequestElementBool("adjustmentNormal", value));
				this->_isNull_adjustmentNormalElement = false;
			}

			else if(strncmp(name, "adjustmentAbnormal", 19) == 0)
			{
				this->_adjustmentAbnormalElement = std::shared_ptr<HistoricRequestElementBool>(new HistoricRequestElementBool("adjustmentAbnormal", value));
				this->_isNull_adjustmentAbnormalElement = false;
			}
			
			else if(strncmp(name, "adjustmentSplit", 16) == 0)
			{
				this->_adjustmentSplitElement = std::shared_ptr<HistoricRequestElementBool>(new HistoricRequestElementBool("adjustmentSplit", value));
				this->_isNull_adjustmentSplitElement = false;
			}

			else
				throw requestEx;
		}

		void HistoricRequest::set(const char* name, int value)
		{
			if(strncmp(name, "maxDataPoints", 14) == 0)
			{
				this->_maxDataPointElement = std::shared_ptr<HistoricRequestElementInt>(new HistoricRequestElementInt("maxDataPoints", value));
				this->_isNull_maxDataPointElement = false;
			}
			
			else
				throw requestEx;
		}

		std::ostream& HistoricRequest::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "HistoricalDataRequest = {" << std::endl;
			
			if(this->_securities->numValues() > 0)
				this->_securities->print(stream, level + 1, spacesPerLevel);

			if(this->_fields->numValues() > 0)
				this->_fields->print(stream, level + 1, spacesPerLevel);

			this->_dtStart->print(stream, level + 1, spacesPerLevel);
			this->_dtEnd->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_periodicityAdjustmentElement)
				this->_periodicityAdjustmentElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_periodicityElement)
				this->_periodicityElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_pricingOptionElement)
				this->_pricingOptionElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_maxDataPointElement)
				this->_maxDataPointElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentNormalElement)
				this->_adjustmentNormalElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentAbnormalElement)
				this->_adjustmentAbnormalElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_adjustmentSplitElement)
				this->_adjustmentSplitElement->print(stream, level + 1, spacesPerLevel);

			if(!this->_isNull_overrideOptionsElement)
				this->_overrideOptionsElement->print(stream, level + 1, spacesPerLevel);
			
			stream << '}' << std::endl;
			return stream;
		}

		Element HistoricRequest::asElement()
		{
			std::shared_ptr<HistoricRequestElement> elem(new HistoricRequestElement(*this));
			return Element(std::dynamic_pointer_cast<ElementPtr>(elem));
		}

	}
}