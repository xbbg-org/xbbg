//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Name.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/ElementPtr.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	std::map<std::string, Name> Name::_globalNameTable;

	Name::Name()
	{
		this->_isNull = true;
	}

	Name::Name(const char* nameString)
	{
		this->_isNull = false;
		this->_name = nameString;
		this->_cname = nameString;
		this->_length = strlen(nameString);

		if(Name::_globalNameTable.find(this->_name) == Name::_globalNameTable.end()) //if name doesn't already exist
			Name::_globalNameTable[this->_name] = *this;
	}

	Name::Name(const Name& original)
	{
		this->_isNull = original._isNull;
		this->_name = original._name;
		this->_cname = this->_name.c_str();
		this->_length = original._length;
	}

	Name& Name::operator=(const Name &rhs)
	{
		if (this != &rhs)
		{
			this->_isNull = rhs._isNull;
			this->_name = rhs._name;
			this->_cname = this->_name.c_str();
			this->_length = rhs._length;
		}
		return *this;
	}

	void Name::clearGlobalNameTable()
	{
		Name::_globalNameTable.clear();
	}

	size_t Name::length() const
	{
		size_t result = this->_name.length();
		return result;
	}

	size_t Name::hash() const
	{
		if(this->_isNull)
			return 0;
		else
		{
			int hash = 17;
			for(size_t i = 0; i < this->_name.length(); i++)
			{
				hash = hash * 23 + this->_name[i];
			}

			return hash;
		}
	}

	Name Name::findName(const char *nameString)
	{
		if(Name::_globalNameTable.find(nameString) == Name::_globalNameTable.end()) //if name doesn't exist
		{
			Name result(nameString); //create the name and insert it into _globalNameTable
			return result;
		}
		else //if name already exists
			return Name::_globalNameTable[nameString];
	}

	bool Name::hasName(const char *nameString)
	{
		return Name::_globalNameTable.find(nameString) != Name::_globalNameTable.end();
	}

	bool Name::isNull() const
	{
		return this->_isNull;
	}


	const char* Name::string() const
	{
		return this->_cname;
	}

	std::ostream& operator<<(std::ostream& stream, const Name& name)
	{
		return stream << name.string();
	}

	bool operator==(const Name& lhs, const char *rhs)
	{
		bool lhsIsNull = lhs.isNull();
		bool rhsIsNull = (rhs == nullptr || rhs[0] == '\0');

		if(lhsIsNull)
			return rhsIsNull;
		else if(rhsIsNull)
			return false;
		else
			return strncmp(lhs.string(), rhs, lhs.length() + 1) == 0;
	}

	bool operator==(const Name& lhs, const Name rhs)
	{
		bool lhsIsNull = lhs.isNull();
		bool rhsIsNull = rhs.isNull();

		if(lhsIsNull)
			return rhsIsNull;
		else if(rhsIsNull)
			return false;
		else
			return strncmp(lhs.string(), rhs.string(), lhs.length() + 1) == 0;
	}

	bool operator==(const char *lhs, const Name& rhs)
	{
		return rhs == lhs;
	}

	bool operator!=(const Name& lhs, const char *rhs)
	{
		return !(lhs == rhs);
	}

	bool operator!=(const Name& lhs, const Name rhs)
	{
		return !(lhs == rhs);
	}

	bool operator!=(const char *lhs, const Name& rhs)
	{
		return rhs == lhs;
	}

	//Note that while the order of this operation is consistent, it's not guaranteed to be lexical (this is the same in the BB API)
	//I made null Names less than Names with any value.  I haven't checked this against what the BB API returns.
	bool operator<(const Name& lhs, const Name& rhs)
	{
		bool lhsIsNull = lhs.isNull();
		bool rhsIsNull = rhs.isNull();

		if(lhsIsNull && rhsIsNull)
			return false;
		else if(lhsIsNull)
			return true;
		else if(rhsIsNull)
			return false;
		else
			return lhs.hash() < rhs.hash();
	}

	bool operator<=(const Name& lhs, const Name& rhs)
	{
		return (lhs < rhs) || (lhs == rhs);
	}

	bool operator>(const Name& lhs, const Name& rhs)
	{
		return !(lhs <= rhs);
	}

	bool operator>=(const Name& lhs, const Name& rhs)
	{
		return !(lhs < rhs);
	}

}