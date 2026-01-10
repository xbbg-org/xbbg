//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/EventHandler.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Event.h"

namespace BEmu
{
	class Session;

	class EventHandler
	{
		public:
			virtual ~EventHandler() = default;
			DLL_EXPORT virtual bool processEvent(const Event& event, Session * session) = 0;
	};
}