//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/SchemaElementDefinition.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/SchemaElementDefinition.h"
#include "BloombergTypes/Element.h"
#include <ostream>

namespace BEmu
{
	SchemaElementDefinition::SchemaElementDefinition(::blpapi_DataType_t datatype)
	{
		this->_datatype = datatype;
		this->_name = Name(Element::toString(datatype));
	}

	SchemaElementDefinition::SchemaElementDefinition(::blpapi_DataType_t datatype, Name name)
	{
		this->_datatype = datatype;
		this->_name = Name(name);
	}

	SchemaElementDefinition::SchemaElementDefinition(const SchemaElementDefinition& arg)
	{
		this->_datatype = arg._datatype;
		this->_name = arg._name;
	}

	SchemaElementDefinition& SchemaElementDefinition::operator=(const SchemaElementDefinition &rhs)
	{
		if(this != &rhs)
		{
			this->_datatype = rhs._datatype;
			this->_name = rhs._name;
		}
		return *this;
	}

	Name SchemaElementDefinition::name() const
	{
		return this->_name;
	}

	std::ostream& SchemaElementDefinition::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		(void)level; (void)spacesPerLevel;
		stream << "Type " << Element::toString(this->_datatype) << std::endl;
		return stream;
	}

	std::ostream& operator<<(std::ostream& stream, const SchemaElementDefinition& element)
	{
		return element.print(stream);
	}
}