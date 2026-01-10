//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/SessionOptions.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"

namespace BEmu
{
	class SessionOptions
	{
		private:
			unsigned short _port;
			const char * _host;

		public:
			DLL_EXPORT void setServerPort(unsigned short port);
			DLL_EXPORT void setServerHost(const char * host);

			DLL_EXPORT const char* serverHost() const;
			DLL_EXPORT unsigned short serverPort() const;

			DLL_EXPORT SessionOptions();
	};
}