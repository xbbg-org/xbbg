//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/RandomDataGenerator.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Types/RandomDataGenerator.h"
#include <algorithm>
#include <cstring>
#include <map>
#include <list>
#include <iostream>
#include "ReferenceDataRequest/ReferenceRequest.h"
#include "ReferenceDataRequest/ReferenceElementArrayChainTickers.h"


namespace BEmu
{
	ObjectType RandomDataGenerator::ReferenceDataFromFieldName(const std::string& fieldName, const std::string& security, bool isOption, std::shared_ptr<ReferenceDataRequest::ReferenceRequest> rreq)
	{
		std::string upper(fieldName);
		std::transform(upper.begin(), upper.end(), upper.begin(), ::toupper);

		if(upper.compare("CHAIN_TICKERS") == 0)
		{
			if(isOption)
				return ObjectType(); //null
			else
			{
				int numPoints = 1;
                std::string dtExp;
				ReferenceDataRequest::OptionalityEnum::EnumType optionality = ReferenceDataRequest::OptionalityEnum::call;

				if(rreq->hasElement("overrides"))
				{
					Element elmOverrides = rreq->getElement("overrides");
					for(size_t i = 0; i < elmOverrides.numValues(); i++)
					{
						Element element = elmOverrides.getValueAsElement(i);

						const char * fieldId = element.getElementAsString("fieldId");
						const char * value = element.getElementAsString("value");
						
						std::string fieldIdUpper(fieldId);
						std::transform(fieldIdUpper.begin(), fieldIdUpper.end(), fieldIdUpper.begin(), ::toupper);
						
						if(fieldIdUpper.compare("CHAIN_POINTS_OVRD") == 0)
						{
							numPoints = atoi(value);
						}
						else if(fieldIdUpper.compare("CHAIN_EXP_DT_OVRD") == 0)
						{
							dtExp = value;
						}
						else if(fieldIdUpper.compare("CHAIN_PUT_CALL_TYPE_OVRD") == 0)
						{
							if(strncmp(value, "P", 2) == 0)
								optionality = ReferenceDataRequest::OptionalityEnum::put;
						}
					}
				}

				std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers> chainP(
					new ReferenceDataRequest::ReferenceElementArrayChainTickers(security, numPoints, dtExp, optionality));
				
				return ObjectType(chainP);
			}
		}
		else if(upper.find("TICKER") != std::string::npos)
		{
			int indexSpace = security.find(' ');
			std::string ticker(security.substr(0, indexSpace));
			return ObjectType(ticker);
		}
		else if(upper.find("OPT_EXPIRE_DT") != std::string::npos)
		{
			if((security.length() >= 6 && security.compare(security.length() - 6, 6, "COMDTY") == 0) || (security.length() >= 5 && security.compare(security.length() - 5, 5, "INDEX") == 0))
			{
				Datetime dt(Datetime::Today());
				dt.addMonths(3);
				return ObjectType(dt);
			}
			else if(isOption)
			{
				int lastIndexSpace = security.find_last_of(' ');
				std::string strDate(security.substr(lastIndexSpace - 15, 6));

				Datetime dt(Datetime::FromYYMMDD(strDate));
				return ObjectType(dt);
			}
			else
			{
				return ObjectType(); //null
			}
		}
		else if(upper.find("TRADEABLE_DT") != std::string::npos)
		{
			Datetime dt(Datetime::Today());
			dt.addMonths(3);
			return ObjectType(dt);
		}
		else
		{
			double value = RandomDataGenerator::RandomDouble();
			return ObjectType(value);
		}
	}

	std::shared_ptr<IntradayBarRequest::IntradayBarTickDataType> RandomDataGenerator::GenerateBarData(const Datetime& date)
	{
        double first = RandomDataGenerator::RandomDouble();
        double second = RandomDataGenerator::RandomDouble();

        double high = first > second ? first : second;
        double low = first > second ? second : first;
        double open = RandomDataGenerator::RandomDouble(low, high);
        double close = RandomDataGenerator::RandomDouble(low, high);

        long volume = RandomDataGenerator::RandomInt(1000000);
		double value = RandomDataGenerator::RandomDouble(1, 10000);
		int numEvents = RandomDataGenerator::RandomInt(10000);

		std::shared_ptr<IntradayBarRequest::IntradayBarTickDataType> result(new IntradayBarRequest::IntradayBarTickDataType(date, open, high, low, close, value, volume, numEvents));
		return result;
	}

	std::map<std::string, ObjectType> RandomDataGenerator::GetMarketDataFields(const std::vector<std::string>& arg)
	{
		std::map<std::string, ObjectType> result;
	
		//A market data response contains at least one of the requested fields, but not necessarilly all of them.
		//  The response contains the requested fields that changed.
		while(result.size() == 0)
		{
			for(std::vector<std::string>::const_iterator ii = arg.begin(); ii != arg.end(); ii++)
			{
				if(RandomDataGenerator::RandomDouble(1, 10) < 3)
				{
					std::string str = *ii;
					ObjectType obj = RandomDataGenerator::MarketDataFromFieldName(str);
					result[str] = obj;
				}
			}
		}
	
		//Market data responses contain extraneous data fields.  The user will not have requested them.
		//  To make this emulator more realistic, I'll add some extraneous fields of different types below.	
		{
			std::string extraDoubleFields[] = { "PREV_SES_LAST_PRICE", "PREV_CLOSE_VALUE_REALTIME", "PRICE_PREVIOUS_CLOSE_RT", "LOW", "LOW_TDY", "PRICE_LOW_RT" };
			const int length = 6;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraDoubleFields[i]))
					result[extraDoubleFields[i]] = ObjectType(RandomDataGenerator::RandomDouble());
			}
		}
	
		{
			std::string extraIntFields[] = { "PX_DISPLAY_FMT_MIN_#_DECIMALS_RT", "PX_DISPLAY_FMT_MAX_#_DECIMALS_RT", "NEWS_HEAT_STORY_FLOW_RT", "BID_SIZE_TDY", "BID_SIZE", "ASK_SIZE_TDY" };	
			const int length = 6;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraIntFields[i]))
					result[extraIntFields[i]] = ObjectType(RandomDataGenerator::RandomInt(100));
			}
		}
	
		{
			std::string extraTimeFields[] = { "SES_START", "LAST_UPDATE_BID_RT", "LAST_UPDATE_ASK_RT", "BID_ASK_TIME", "LAST_TRADE_RECEIVED_TIME_RT" };
			const int length = 5;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraTimeFields[i]))
					result[extraTimeFields[i]] = ObjectType(RandomDataGenerator::RandomTime());
			}
		}
	
		{
			std::string extraDateFields[] = { "PRICE_52_WEEK_HIGH_DATE_RT", "PRICE_52_WEEK_LOW_DATE_RT", "PREV_TRADING_DT_REALTIME", "TRADING_DT_REALTIME" };
			const int length = 4;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraDateFields[i]))
					result[extraDateFields[i]] = ObjectType(RandomDataGenerator::RandomDate());
			}
		}
	
		{
			std::string extraDateTimeFields[] = { "TRADE_UPDATE_STAMP_RT" };
			const int length = 1;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraDateTimeFields[i]))
					result[extraDateTimeFields[i]] = ObjectType(RandomDataGenerator::RandomDate());
			}
		}
	
		{
			std::string extraStringFields[] = { "MKTDATA_EVENT_TYPE", "LAST_PX_LOCAL_EXCH_SOURCE_RT", "CLOSE_LOCAL_SOURCE_RT", "BID_PX_LOCAL_EXCH_SOURCE_RT", "HIGH_LOCAL_SOURCE_RT" };
			const int length = 5;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraStringFields[i]))
					result[extraStringFields[i]] = ObjectType(RandomDataGenerator::RandomDate());
			}
		}
	
		{
			std::string extraBoolFields[] = { "IND_BID_FLAG", "IND_ASK_FLAG", "SHORT_SALE_THRESHOLD_REALTIME", "NO_SHORT_SELL_REALTIME", "RT_EXCH_TRADE_STATUS" };
			const int length = 5;
			for(int i = 0; i < length; i++)
			{
				if(!result.count(extraBoolFields[i]))
					result[extraBoolFields[i]] = ObjectType(RandomDataGenerator::RandomDate());
			}
		}

		return result;
	}

	ObjectType RandomDataGenerator::MarketDataFromFieldName(const std::string& arg)
	{
		std::string arg_lower(arg);
		for(unsigned int i = 0; i < arg_lower.size(); i++)
		{
			arg_lower[i] = std::tolower(arg_lower[i]);
		}

		std::size_t searchDate = arg_lower.find("date");
		std::size_t searchTime = arg_lower.find("time");

		ObjectType oresult;
		if(searchDate != std::string::npos)
        {
            Datetime dt = Datetime::Today();
            dt.addDays(-RandomDataGenerator::RandomInt(1, 100));
            oresult = ObjectType(dt);
        }
		else if(searchTime != std::string::npos)
        {
            Datetime dt = Datetime::Now();
            dt.addMinutes(-RandomDataGenerator::RandomInt(1, 100));
            Datetime dtResult(dt.hours(), dt.minutes(), dt.seconds(), 0);
            oresult = ObjectType(dtResult);
        }
		else
		{
			oresult = ObjectType(RandomDataGenerator::RandomDouble());
		}

		return oresult;
	}

	bool RandomDataGenerator::ShouldIncludeQuote()
	{
		return RandomDataGenerator::RandomDouble() < 70;
	}

	int RandomDataGenerator::TimeBetweenMarketDataEventsMs() { return RandomDataGenerator::RandomInt(500, 2000) + 100; }

	int RandomDataGenerator::IntradayTickIntervalInMinutes()
	{
		int minutes = RandomDataGenerator::RandomInt(1, 30);
		return minutes;
	}

	int RandomDataGenerator::IntradayTickTradeSize()
	{
		return RandomDataGenerator::RandomInt(5) * 100;
	}

	int RandomDataGenerator::Strike()
	{
		return RandomDataGenerator::RandomInt(20) * 5;
	}

	Datetime RandomDataGenerator::RandomDatetime()
    {
        Datetime dt = Datetime::Now();
        dt.addDays(RandomDataGenerator::RandomInt(100));
        dt.addSeconds(RandomDataGenerator::RandomInt(1000));
        return dt;
    }

	Datetime RandomDataGenerator::RandomDate()
    {
        Datetime dt = Datetime::Today();
        dt.addDays(RandomDataGenerator::RandomInt(100));
        return dt;
    }

	Datetime RandomDataGenerator::RandomTime()
    {
        Datetime dt = Datetime::Now();
        dt.addSeconds(RandomDataGenerator::RandomInt(1000));
        return Datetime(dt.hours(), dt.minutes(), dt.seconds(), 0);
    }

	double RandomDataGenerator::RandomDouble()
	{
		return RandomDataGenerator::RandomDouble(1, 100);
	}

	double RandomDataGenerator::RandomDouble(double min, double max)
	{
		//note that rand() is seeded in the Session constructor
		return ((double)rand() / ((double)RAND_MAX + 1.0)) * (max - min + 1) + min;
	}

	int RandomDataGenerator::RandomInt(int min, int max)
	{
		//note that rand() is seeded in the Session constructor
		return (int)( ((double)rand() / ((double)RAND_MAX + 1.0)) * (max - min + 1) + min );
	}

	int RandomDataGenerator::RandomInt(int max)
	{
		return RandomDataGenerator::RandomInt(1, max);
	}

	char RandomDataGenerator::RandomChar()
	{
		return (char)('A' + RandomDataGenerator::RandomInt(0, 25));
	}

	std::string RandomDataGenerator::RandomString(int length)
	{
		std::stringstream ss;

		for(int i = 0; i < length - 1; i++)
		{
			ss << RandomDataGenerator::RandomChar();
		}
		ss << '\0';

		return ss.str();
	}

	std::string RandomDataGenerator::RandomString()
	{
		int length = RandomDataGenerator::RandomInt(2, 11);
		return RandomDataGenerator::RandomString(length);
	}

	bool RandomDataGenerator::RandomBool()
	{
		return RandomDataGenerator::RandomInt(1, 2) == 2;
	}
}