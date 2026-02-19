//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/MarketDataRequest/MarketMessageSessionOpened.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/MessagePtr.h"

namespace BEmu
{
	namespace MarketDataRequest
	{
		class MarketMessageSessionOpened : public MessagePtr
		{
			public:
				MarketMessageSessionOpened();
				virtual const char* topicName() const;
		};
	}
}