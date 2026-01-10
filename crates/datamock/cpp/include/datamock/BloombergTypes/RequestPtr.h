//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/RequestPtr.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Element.h"
#include "BloombergTypes/CorrelationId.h"
#include <exception>

namespace BEmu
{
	class Name;
	class Session;
	class EventPtr;
	class CorrelationId;
	class Datetime;

	class RequestPtr
	{
		public:
			enum RequestTypeEnum { historic, reference, intradayTick, intradayBar };

		private:
			//Session::sendRequest needs to set the correlationId of a given request.  The API marks the Request parameter as a const, so the mutable here overrides that.
			mutable CorrelationId _correlationId;

		protected:	
			RequestPtr();
			RequestPtr(const RequestPtr &src);
			RequestTypeEnum _requestType;
	
		public:
			
			virtual ~RequestPtr();

			class RequestException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} requestEx;

			CorrelationId getCorrelationId() const;
			void setCorrelationId(const CorrelationId& arg);
			RequestTypeEnum getRequestType() const;
			
			virtual void append(const char* name, const char* value);
			void append(const Name& name, const char* value);

			virtual void set(const char* name, const char* value);
			void set(const Name& name, const char* value);

			virtual void set(const char* name, bool value);
			void set(const Name& name, bool value);

			virtual void set(const char* name, int value);
			void set(const Name& name, int value);

			virtual void set(const char* name, const Datetime& value);
			void set(const Name& name, const Datetime& value);

			virtual Element getElement(const char* name);
			Element getElement(const Name& name);

			virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;

			// The C# version of the code has a "HasElement(string)" method in the Request class.  The C++ version of the code doesn't.
			//    In the C++ version, an equivalent call would be "request.asElement().hasElement(string)".
			//    Given that the caller creates a request object, the caller should be aware of whether or not a Request object has some given Element,
			//      I find the Request.hasElement(...) methods unnecessary.  (Maybe the API developers thought the same way)
			//    Note that I haven't implemented all of the asElement()s for the Requests.  I can't think of a use-case for asElements()s.
	};

	std::ostream& operator<<(std::ostream& stream, const RequestPtr &request);
}