//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Request.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Request.h"
#include <ostream>

namespace BEmu
{
	Request::Request()
	{
	}

	Request::Request(std::shared_ptr<RequestPtr> ptr) : _shptr(ptr)
	{
	}

	Request::Request(const Request& arg) : _shptr(arg._shptr)
	{
	}

	Request& Request::operator=(const Request &rhs)
	{
		if (this != &rhs)
		{
			this->_shptr = std::shared_ptr<RequestPtr>(rhs._shptr);
		}
		return *this;
	}

	Request::~Request()
	{
	}
	
	std::shared_ptr<RequestPtr> Request::getRequestPtr() const
	{
		return this->_shptr;
	}

	void Request::append(const char* name, const char* value)
	{
		this->_shptr->append(name, value);
	}

	void Request::append(const Name& name, const char* value)
	{
		this->_shptr->append(name, value);
	}


	void Request::set(const char* name, const char* value)
	{
		this->_shptr->set(name, value);
	}

	void Request::set(const Name& name, const char* value)
	{
		this->_shptr->set(name, value);
	}


	void Request::set(const char* name, const Datetime& value)
	{
		this->_shptr->set(name, value);
	}
	void Request::set(const Name& name, const Datetime& value)
	{
		this->_shptr->set(name, value);
	}


	void Request::set(const char* name, bool value)
	{
		this->_shptr->set(name, value);
	}

	void Request::set(const Name& name, bool value)
	{
		this->_shptr->set(name, value);
	}


	void Request::set(const char* name, int value)
	{
		this->_shptr->set(name, value);
	}

	void Request::set(const Name& name, int value)
	{
		this->_shptr->set(name, value);
	}


	Element Request::getElement(const char* name)
	{
		return this->_shptr->getElement(name);
	}

	Element Request::getElement(const Name& name)
	{
		return this->_shptr->getElement(name);
	}

	std::ostream& Request::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		this->_shptr->print(stream, level, spacesPerLevel);
		return stream;
	}

	std::ostream& operator<<(std::ostream& stream, const Request &request)
	{
		request.print(stream);
		return stream;
	}

}