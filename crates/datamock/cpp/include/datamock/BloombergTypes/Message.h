//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Message.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include <exception>

namespace BEmu
{
	class Name;
	class MessagePtr;
	class CorrelationId;
	class Element;
	class Datetime;

	class Message
	{
		private:
			std::shared_ptr<MessagePtr> _ptr;

		public:
			Message();
			virtual ~Message() = default;
			Message(std::shared_ptr<MessagePtr> ptr);

			class MessageException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} messageEx;
			
			DLL_EXPORT Message(const Message& arg);
			DLL_EXPORT Message& operator=(const Message &rhs);

			DLL_EXPORT CorrelationId correlationId() const;
			DLL_EXPORT Name messageType() const;
			DLL_EXPORT virtual const char* topicName() const;
			DLL_EXPORT virtual size_t numElements() const;
			DLL_EXPORT virtual const Element asElement() const;

			DLL_EXPORT const Element getElement(const Name& name) const;
			DLL_EXPORT const Element getElement(const char* name) const;

			DLL_EXPORT bool hasElement(const Name& name, bool excludeNullElements = false) const;
			DLL_EXPORT bool hasElement(const char* name, bool excludeNullElements = false) const;
			
			DLL_EXPORT bool getElementAsBool(const Name& name) const;
			DLL_EXPORT bool getElementAsBool(const char* name) const;

			DLL_EXPORT int getElementAsInt32(const Name& name) const;
			DLL_EXPORT int getElementAsInt32(const char* name) const;

			DLL_EXPORT long getElementAsInt64(const Name& name) const;
			DLL_EXPORT long getElementAsInt64(const char* name) const;

			DLL_EXPORT float getElementAsFloat32(const Name& name) const;
			DLL_EXPORT float getElementAsFloat32(const char* name) const;

			DLL_EXPORT double getElementAsFloat64(const Name& name) const;
			DLL_EXPORT double getElementAsFloat64(const char* name) const;

			DLL_EXPORT Datetime getElementAsDatetime(const Name& name) const;
			DLL_EXPORT Datetime getElementAsDatetime(const char* name) const;

			DLL_EXPORT const char* getElementAsString(const Name& name) const;
			DLL_EXPORT const char* getElementAsString(const char* name) const;

			DLL_EXPORT virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
	};

	DLL_EXPORT std::ostream& operator<<(std::ostream& stream, const Message &message);
}