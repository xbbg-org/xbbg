//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/ObjectType.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Types/ObjectType.h"
#include "BloombergTypes/ElementPtr.h"
#include <iostream>
#include <stdlib.h>
#include "ReferenceDataRequest/ReferenceElementArrayChainTickers.h"
#include "Types/DisplayFormats.h"

namespace BEmu
{
	ObjectType::ObjectType()
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_otype = eNothing;
	}

	ObjectType::ObjectType(double arg)
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_dbl = arg;
		this->_otype = eDouble;
	}

	ObjectType::ObjectType(int arg)
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_int = arg;
		this->_otype = eInt;
	}

	ObjectType::ObjectType(bool arg)
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_bool = arg;
		this->_otype = eBool;
	}

	ObjectType::ObjectType(const std::string& arg)
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_str = arg;
		this->_otype = eString;
	}

	ObjectType::ObjectType(const char * arg)
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_str = std::string(arg);
		this->_otype = eString;
	}

	ObjectType::ObjectType(const Datetime& arg)
		: _chainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>())
	{
		this->_datetime = arg;
		this->_otype = eDatetime;
	}

	ObjectType::ObjectType(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers> arg)
		: _chainTickers(arg)
	{
		this->_otype = eChainTickers;
	}

	ObjectType::~ObjectType()
	{
	}

	bool ObjectType::IsNull() const
	{
		return this->_otype == eNothing;
	}

	ObjectType& ObjectType::operator=(const ObjectType &rhs)
	{
		if (this != &rhs)
		{
			this->_bool = rhs._bool;
			this->_datetime = rhs._datetime;
			this->_dbl = rhs._dbl;
			this->_int = rhs._int;
			this->_otype = rhs._otype;
			this->_str = rhs._str;

			this->_chainTickers = rhs._chainTickers;
		}
		return *this;
	}

	ObjectType::ObjectType(const ObjectType& arg)
		: _chainTickers(arg._chainTickers)
	{
		this->_bool = arg._bool;
		this->_datetime = arg._datetime;
		this->_dbl = arg._dbl;
		this->_int = arg._int;
		this->_otype = arg._otype;
		this->_str = arg._str;
	}

	ObjectType::ObjectTypeEnum ObjectType::GetType() const
	{
		return this->_otype;
	}

	bool ObjectType::TryGetDouble(double &arg) const
	{
		arg = this->_dbl;
		return this->_otype == eDouble;
	}

	bool ObjectType::TryGetInt(int &arg) const
	{
		arg = this->_int;
		return this->_otype == eInt;
	}

	bool ObjectType::TryGetBool(bool &arg) const
	{
		arg = this->_bool;
		return this->_otype == eBool;
	}

	bool ObjectType::TryGetString(std::string& arg) const
	{
		arg = this->_str;
		return this->_otype == eString;
	}

	bool ObjectType::TryGetDatetime(Datetime& arg) const
	{
		arg = this->_datetime;
		return this->_otype == eDatetime;
	}

	bool ObjectType::TryGetChainTickers(std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>& arg) const
	{
		arg = std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers>(this->_chainTickers);
		return this->_otype == eChainTickers;
	}


	double ObjectType::ValueAsDouble() const
	{
		return this->_dbl;
	}

	int ObjectType::ValueAsInt() const
	{
		return this->_int;
	}

	bool ObjectType::ValueAsBool() const
	{
		return this->_bool;
	}

	std::string ObjectType::ValueAsString() const
	{
		return this->_str;
	}

	Datetime ObjectType::ValueAsDatetime() const
	{
		return this->_datetime;
	}

	std::shared_ptr<ReferenceDataRequest::ReferenceElementArrayChainTickers> ObjectType::ValueAsChainTickers() const
	{
		return this->_chainTickers;
	}

	std::string ObjectType::ToString() const
	{
		switch(this->_otype)
		{
			case ObjectType::eBool:
				return this->_bool ? "true" : "false";

			case ObjectType::eDatetime:
				return DisplayFormats::ToMMddYYWithSlashes(this->_datetime);

			case ObjectType::eDouble:
			{
				std::stringstream ss;
				ss << this->_dbl;
				return ss.str();
			}

			case ObjectType::eInt:
			{
				std::stringstream ss;
				ss << this->_int;
				return ss.str();
			}
				
			case ObjectType::eString:
			{
				std::string result = this->_str;
				return result;
			}

			case ObjectType::eChainTickers:
			{
				std::stringstream ss;
				this->_chainTickers->print(ss);
				return ss.str();
			}

			default:
				throw objectTypeEx;
		}
	}

}