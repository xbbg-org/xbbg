//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Types/BEmuTimer.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <thread>
#include <mutex>
#include <chrono>
#include <vector>
#include <memory>

namespace BEmu
{
	class BEmuTimerFunction;

	namespace RunType
	{
		enum RunTypeEnum { neverRun = 0, runImmediately = 1 };
	};

	//I built this timer class to work similar to C#'s System.Threading.Timer class
	//  In C#, you give the object a delegate (function pointer) to run, tell it how long to wait before running, and how long between runs to wait.
	//  Using BEmuTimer, you give the object a class with a Run(BEmuTimer * timer) function instead of a function pointer.  The rest is the same.
	//With both the C++ and C# timers, the function that you specify can update its own timer.
	//  This is not the case with the timer I use in the Java version.
	class BEmuTimer
	{
		private:
			std::shared_ptr<BEmuTimerFunction> _toRun;
			bool _isRunning;
			std::mutex _syncroot;

			std::vector<std::thread> _threadGroup;

			int _msecsToStart, _msecsToRestart;
			RunType::RunTypeEnum _runStart, _runRestart;
			bool _useRunTypeStart, _useRunTypeRestart;

			void pStart(); //called internally.  This is run on a new thread.  Most of the work of this class happens here.

		public:
			BEmuTimer(std::shared_ptr<BEmuTimerFunction> toRun); //toRun is an object with a Run() function.  The timer calls this Run() function.

			//All times are in milleseconds (1000 milleseconds = 1 second)
			void start(int msecsToStart, int msecsToRestart); //starts the timer after msecsToStart milleseconds, and reruns it every msecsToRestart milleseconds
			void start(RunType::RunTypeEnum start, int msecsToRestart); //starts the timer either immediately or never, and reruns it every msecsToRestart milleseconds
			void start(int msecsToStart, RunType::RunTypeEnum restart); //starts the timer after msecsToStart milleseconds, and reruns it every msecsToRestart milleseconds

			//void start(RunType::RunTypeEnum start, RunType::RunTypeEnum restart); //starts the timer either immediately or never, and reruns it either immediately or never
			//  Kinda useless.

			void reset(int msecsToRestart); //changes how often the Run() function is called
			//void reset(RunType::RunTypeEnum restart); //changes how often the Run() function is called
			//  Kinda useless.

			//Stops the timer
			//  This does not kill the thread.
			//  It instead sets a flag within the thread that tells it that it can stop (exit its while loop)
			//  The maximum amount of time between calling stop() and the thread actually exiting is this->_msecsToRestart
			//  stop() does not block.
			void stop();

			void stopAndWait();
	};
}
