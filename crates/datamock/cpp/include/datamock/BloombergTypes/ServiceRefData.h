//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/ServiceRefData.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Service.h"
#include <exception>

namespace BEmu
{
	class RequestPtr;
	class Request;

	class ServiceRefData : Service
	{
		public:
			~ServiceRefData() override = default;
			const char* name() const override;

			std::shared_ptr<RequestPtr> createRequestPtr(const char* operation) const;
			Request createRequest(const char* operation) const override;

			class ServiceRefDataException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} serviceRefDataEx;
	};
}