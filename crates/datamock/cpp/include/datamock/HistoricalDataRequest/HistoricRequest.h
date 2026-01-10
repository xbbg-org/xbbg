//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/HistoricalDataRequest/HistoricRequest.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/RequestPtr.h"
#include <vector>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		namespace HistDataPeriodicityAdjustmentEnum
		{
			enum EnumType { actual, calendar, fiscal };
		}

		namespace HistDataPeriodicityEnum
		{
			enum EnumType { daily, weekly, monthly, quarterly, semi_annually, yearly };
		}

		namespace PricingOptionEnum
		{
			enum EnumType { price, yield };
		}

		namespace OverrideOptionsEnum
		{
			enum EnumType { closingPrice, averagePrice };
		}

		class HistoricRequestElementStringArray;
		class HistoricRequestElementDate;
		class HistoricRequestElementBool;
		class HistoricRequestElementInt;
		class HistoricRequestElementString;

		class HistoricRequest : public RequestPtr
		{
			private:
				std::shared_ptr<HistoricRequestElementStringArray> _securities, _fields;
				std::shared_ptr<HistoricRequestElementDate> _dtStart, _dtEnd;
				std::shared_ptr<HistoricRequestElementBool> _adjustmentNormalElement, _adjustmentAbnormalElement, _adjustmentSplitElement;
				std::shared_ptr<HistoricRequestElementInt> _maxDataPointElement;
				std::shared_ptr<HistoricRequestElementString> _periodicityAdjustmentElement, _periodicityElement, _overrideOptionsElement, _pricingOptionElement;

				bool _isNull_securities, _isNull_fields;
				bool _isNull_dtStart, _isNull_dtEnd;
				bool _isNull_adjustmentNormalElement, _isNull_adjustmentAbnormalElement, _isNull_adjustmentSplitElement;
				bool _isNull_maxDataPointElement;
				bool _isNull_periodicityAdjustmentElement, _isNull_periodicityElement, _isNull_overrideOptionsElement, _isNull_pricingOptionElement;

				HistDataPeriodicityAdjustmentEnum::EnumType _periodicityAdjustment;
				HistDataPeriodicityEnum::EnumType _periodicity;
				PricingOptionEnum::EnumType _pricingOption;
				OverrideOptionsEnum::EnumType _overrideOptions;

			public:
				using RequestPtr::set;

				HistoricRequest();
				~HistoricRequest();

				std::vector<std::string> securities() const;
				std::vector<std::string> fields() const;
				Datetime dtStart() const;
				Datetime dtEnd() const;

				std::vector<Datetime> getDates() const;
				std::vector<Datetime> getDatesBeforeMaxPoints() const;
				
				bool hasStartDate() const;
				bool hasEndDate() const;

				virtual void append(const char* name, const char* value);

				virtual void set(const char* name, const char* value);
				virtual void set(const char* name, bool value);
				virtual void set(const char* name, int value);

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}