//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/IntradayTickRequest/IntradayTickRequestElementInt.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "IntradayTickRequest/IntradayTickRequestElementInt.h"
#include "IntradayTickRequest/IntradayTickRequestElementString.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "Types/IndentType.h"

namespace BEmu
{
	namespace IntradayTickRequest
	{
		IntradayTickRequestElementInt::IntradayTickRequestElementInt(const std::string& elementName, int ivalue) :
			IntradayTickRequestElementString(elementName, ivalue)
		{
			this->_ivalue = ivalue;
		}

		IntradayTickRequestElementInt::~IntradayTickRequestElementInt()
		{
		}

		int IntradayTickRequestElementInt::getInt() const
		{
			return this->_ivalue;
		}
	}
}