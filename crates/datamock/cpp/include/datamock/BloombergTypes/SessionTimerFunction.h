//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/SessionTimerFunction.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "Types/BEmuTimerFunction.h"
#include <memory>

namespace BEmu
{
	class Session;
	class EventHandler;
	class BEmuTimer;

	class SessionTimerFunction : public BEmuTimerFunction
	{
		private:
			Session * _session;
			EventHandler * _eventHandler;

		public:
			SessionTimerFunction(Session * session, EventHandler * eventHandler);
			virtual void Run(BEmuTimer * timer);
	};
}