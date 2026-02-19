//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/ServiceRefData.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/ServiceRefData.h"
#include "BloombergTypes/RequestPtr.h"
#include "BloombergTypes/Service.h"
#include <cstring>

#include "IntradayTickRequest/IntradayTickRequest.h"
#include "IntradayBarRequest/IntradayBarRequest.h"
#include "HistoricalDataRequest/HistoricRequest.h"
#include "ReferenceDataRequest/ReferenceRequest.h"

namespace BEmu
{
	const char* ServiceRefData::name() const
	{
		return "//blp/refdata";
	}

	Request ServiceRefData::createRequest(const char* operation) const
	{
		std::shared_ptr<RequestPtr> reqp(this->createRequestPtr(operation));
		Request result(reqp);
		return result;
	}

	std::shared_ptr<RequestPtr> ServiceRefData::createRequestPtr(const char* operation) const
	{
		if(strncmp(operation, "HistoricalDataRequest", 21) == 0)
		{
			std::shared_ptr<RequestPtr> result(new HistoricalDataRequest::HistoricRequest());
			return result;
		}
		else if(strncmp(operation, "ReferenceDataRequest", 21) == 0)
		{
			std::shared_ptr<RequestPtr> result(new ReferenceDataRequest::ReferenceRequest());
			return result;
		}
		else if(strncmp(operation, "IntradayTickRequest", 20) == 0)
		{
			std::shared_ptr<RequestPtr> result(new IntradayTickRequest::IntradayTickRequest(*this));
			return result;
		}
		else if(strncmp(operation, "IntradayBarRequest", 19) == 0)
		{
			std::shared_ptr<RequestPtr> result(new IntradayBarRequest::IntradayBarRequest(*this));
			return result;
		}
		else
		{
			throw serviceRefDataEx;
		}
	}
}