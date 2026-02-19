//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/BEmuTimer.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Types/BEmuTimer.h"
#include "Types/BEmuTimerFunction.h"

namespace BEmu
{
	BEmuTimer::BEmuTimer(std::shared_ptr<BEmuTimerFunction> toRun)
	{
		this->_toRun = toRun;
		this->_isRunning = false;
	}

	void BEmuTimer::pStart()
	{
		//load members into local variables in a critical section to prevent concurrency issues
		this->_syncroot.lock();
			bool isRunning = this->_isRunning;
			bool useRunTypeStart = this->_useRunTypeStart;
			bool useRunTypeRestart = this->_useRunTypeRestart;
			int msecsToRestart = this->_msecsToRestart;
			int msecsToStart = this->_msecsToStart;
			RunType::RunTypeEnum runStart = this->_runStart;
			RunType::RunTypeEnum runRestart = this->_runRestart;
		this->_syncroot.unlock();

		if(useRunTypeStart)
		{
			if(runStart == RunType::runImmediately)
			{
				//do nothing, the loop runs this->_toRun->Run() immediately and then sleeps
			}
			else if(runStart == RunType::neverRun)
				isRunning = false; //flag to skip the loop, effectively killing the thread
		}
		else //use msecsToStart
		{
			if(msecsToStart > 0) //time to wait before the first call
				std::this_thread::sleep_for(std::chrono::milliseconds(msecsToStart));
		}

		while(isRunning)
		{
			this->_toRun->Run(this); //run the actual code

			if(msecsToRestart > 0) //sleep a set amount of time
			{
				std::this_thread::sleep_for(std::chrono::milliseconds(msecsToRestart));
			}

			//in case the user reset() the timer, reload the isRunning and msecsToRestart variables
			this->_syncroot.lock();
				isRunning = this->_isRunning;
				msecsToRestart = this->_msecsToRestart;
				useRunTypeRestart = this->_useRunTypeRestart;
				runRestart = this->_runRestart;
			this->_syncroot.unlock();

			if(useRunTypeRestart) //the user can flag the thread to stop using reset(RunType::neverRun), or just call stop()
			{
				if(runRestart == RunType::neverRun)
					isRunning = false; //flag to exit the loop, effectively killing the thread
				else if(runRestart == RunType::runImmediately)
					msecsToRestart = 0;
			}
		}

		this->_syncroot.lock();
			this->_isRunning = false;
		this->_syncroot.unlock();

		//when control reaches here, the thread dies
	}

	//Normally: Use this to run your function immediately and then wait a specific amount of time in between runs
	void BEmuTimer::start(RunType::RunTypeEnum start, int msecsToRestart)
	{
		this->_syncroot.lock();
			this->_msecsToRestart = msecsToRestart;
			this->_runStart = start;
			this->_useRunTypeStart = true;
			this->_useRunTypeRestart = false;
			this->_isRunning = start == RunType::runImmediately;
		this->_syncroot.unlock();

		if(start == RunType::runImmediately)
			this->_threadGroup.emplace_back([this]() { this->BEmuTimer::pStart(); });
	}

	//Normally: Use this to wait a specific amount of time before running your function, and then quitting.
	void BEmuTimer::start(int msecsToStart, RunType::RunTypeEnum restart)
	{
		this->_syncroot.lock();
			this->_isRunning = true;
			this->_msecsToStart = msecsToStart;
			this->_useRunTypeStart = false;
			this->_useRunTypeRestart = true;
			this->_runRestart = restart;
		this->_syncroot.unlock();

		this->_threadGroup.emplace_back([this]() { this->BEmuTimer::pStart(); });
	}

	//Normally: Use this to wait a specific amount of time before running your function, and then wait a specific amount of time in between runs.
	void BEmuTimer::start(int msecsToStart, int msecsToRestart)
	{
		this->_syncroot.lock();
			this->_isRunning = true;
			this->_msecsToStart = msecsToStart;
			this->_msecsToRestart = msecsToRestart;
			this->_useRunTypeStart = false;
			this->_useRunTypeRestart = false;
		this->_syncroot.unlock();

		this->_threadGroup.emplace_back([this]() { this->BEmuTimer::pStart(); });
	}

	//Use this to change how often your function runs.  Note that your function can call this function.
	void BEmuTimer::reset(int msecsToRestart)
	{
		bool shouldStartNewThread = false;

		this->_syncroot.lock();
			this->_useRunTypeRestart = false;
			this->_msecsToRestart = msecsToRestart;

			if(!this->_isRunning)
			{
				this->_isRunning = true;
				this->_msecsToStart = 0;
				this->_useRunTypeStart = false;

				shouldStartNewThread = true;
			}
		this->_syncroot.unlock();

		if(shouldStartNewThread)
			this->_threadGroup.emplace_back([this]() { this->BEmuTimer::pStart(); });
	}

	//Stops the timer without without blocking.  The thread will eventually exit.
	void BEmuTimer::stop()
	{
		this->_syncroot.lock();
			this->_isRunning = false;
		this->_syncroot.unlock();
	}

	void BEmuTimer::stopAndWait()
	{
		this->_syncroot.lock();
			this->_isRunning = false;
		this->_syncroot.unlock();

		// Wait for all threads to stop running
		for (auto& t : this->_threadGroup) {
			if (t.joinable()) {
				t.join();
			}
		}
	}
}
