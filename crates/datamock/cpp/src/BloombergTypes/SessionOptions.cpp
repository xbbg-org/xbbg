//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/SessionOptions.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/SessionOptions.h"

namespace BEmu
{
	void SessionOptions::setServerPort(unsigned short port)
	{
		this->_port = port;
	}

	void SessionOptions::setServerHost(const char * host)
	{
		this->_host = host;
	}

	const char* SessionOptions::serverHost() const
	{
		return this->_host;
	}

	unsigned short SessionOptions::serverPort() const
	{
		return this->_port;
	}

	SessionOptions::SessionOptions()
	{
	}
}