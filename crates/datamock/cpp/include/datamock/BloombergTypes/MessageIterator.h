//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/MessageIterator.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include <exception>
#include <vector>

namespace BEmu
{
	class Event;
	class Message;
	class MessagePtr;

	//This class mirrors the BloombergLP.blpapi.MessageIterator as declared in blpapi_event.h (there's no blpapi_message_iterator.h file)
	class MessageIterator
	{
		private:
			std::vector< std::shared_ptr<MessagePtr> > _listP;
			int _position;

		public:
			DLL_EXPORT bool next();
			DLL_EXPORT bool isValid() const;
			DLL_EXPORT Message message(bool createClonable = false) const;

			DLL_EXPORT MessageIterator(const Event& evt);
			DLL_EXPORT ~MessageIterator(); //when the messageIterator goes out of scope in the actual BB API, its elements and messages are deleted
	};
}