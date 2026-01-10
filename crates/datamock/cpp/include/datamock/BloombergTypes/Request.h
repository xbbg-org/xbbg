//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Request.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/RequestPtr.h"

namespace BEmu
{
	class Request
	{
		private:

			//The way I'm doing polymorphism is a little broken because actual Bloomberg API functions like Service.createRequest(...) return a value rather than a reference.
			//  Because I use several derived Request classes to emulate the behavior of the API's *one* Request object, I have some work to do to ensure the caller is calling the right functions.
			//  When casting from a derived-Request to this parent-Request, I internally keep a pointer to the derived-Request so that I know how to pass around function calls.
			//  If each Request object keeps a pointer to some internal RequestPtr object, the user doesn't have to know that I've implemented the Request type as a collection of derived classes.
			std::shared_ptr<RequestPtr> _shptr;

		public:
			std::shared_ptr<RequestPtr> getRequestPtr() const;

			DLL_EXPORT Request();

			Request(std::shared_ptr<RequestPtr> ptr);

			DLL_EXPORT Request(const Request& arg);
			DLL_EXPORT Request& operator=(const Request &rhs);

			DLL_EXPORT ~Request();
			
			DLL_EXPORT void append(const char* name, const char* value);
			DLL_EXPORT void append(const Name& name, const char* value);

			DLL_EXPORT void set(const char* name, const char* value);
			DLL_EXPORT void set(const Name& name, const char* value);

			DLL_EXPORT void set(const char* name, const Datetime& value);
			DLL_EXPORT void set(const Name& name, const Datetime& value);

			DLL_EXPORT void set(const char* name, bool value);
			DLL_EXPORT void set(const Name& name, bool value);

			DLL_EXPORT void set(const char* name, int value);
			DLL_EXPORT void set(const Name& name, int value);

			DLL_EXPORT Element getElement(const char* name);
			DLL_EXPORT Element getElement(const Name& name);

			DLL_EXPORT std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
	};

	DLL_EXPORT std::ostream& operator<<(std::ostream& stream, const Request &request);
}