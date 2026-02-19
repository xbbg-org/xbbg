//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/IntradayTickRequest/IntradayTickRequestElementInt.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "IntradayTickRequest/IntradayTickRequestElementString.h"

namespace BEmu
{
	namespace IntradayTickRequest
	{
		class IntradayTickRequestElementInt : public IntradayTickRequestElementString
		{
			private:
				int _ivalue;

			public:
				IntradayTickRequestElementInt(const std::string& elementName, int ivalue);
				~IntradayTickRequestElementInt();

				int getInt() const;
		};
	}
}