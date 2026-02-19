//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Types/BEmuTimerFunction.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

namespace BEmu
{
	class BEmuTimer;

	class BEmuTimerFunction
	{
		public:
			virtual void Run(BEmuTimer * timer) = 0;
			virtual ~BEmuTimerFunction() { }
	};
}