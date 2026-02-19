//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/MessagePtr.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Name.h"
#include "BloombergTypes/CorrelationId.h"
#include <stack>

namespace BEmu
{
	class Datetime;
	class Message;
	class ElementPtr;

	//See my explanation of the RequetPtr class in Request.h for an explanation of this class
	class MessagePtr
	{
		private:
			CorrelationId _correlationId;
			Name _messageType;

		protected:
			MessagePtr(const Name& messageType, const CorrelationId& corr);

		public:

			virtual ~MessagePtr();

			class MessageException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} messageEx;

			CorrelationId correlationId() const;
			Name messageType() const;
			virtual const char* topicName() const;
			
			std::shared_ptr<ElementPtr> getElement(const Name& name) const;
			virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;
			virtual std::shared_ptr<ElementPtr> asElement() const;

			bool hasElement(const Name& name, bool excludeNullElements = false) const;
			virtual bool hasElement(const char* name, bool excludeNullElements = false) const;
			virtual size_t numElements() const;
			
			bool getElementAsBool(const char* name) const;
			int getElementAsInt32(const char* name) const;
			long getElementAsInt64(const char* name) const;
			float getElementAsFloat32(const char* name) const;
			double getElementAsFloat64(const char* name) const;
			Datetime getElementAsDatetime(const char* name) const;
			const char* getElementAsString(const char* name) const;

			virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
	};

	inline std::ostream& operator<< (std::ostream& out, const MessagePtr& msg)
	{
		msg.print(out);
		return out;
	}
}