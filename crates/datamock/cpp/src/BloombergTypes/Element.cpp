//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Element.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Name.h"
#include "BloombergTypes/Element.h"
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/SchemaElementDefinition.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	Element::Element()
		: _ptr(std::shared_ptr<ElementPtr>())
	{
	}

	Element::Element(const Element& arg)
		: _ptr(arg._ptr)
	{
	}

	Element::Element(std::shared_ptr<ElementPtr> arg)
		: _ptr(arg)
	{
	}

	Element& Element::operator=(const Element &rhs)
	{
		if (this != &rhs)
		{
			this->_ptr = rhs._ptr;
		}
		return *this;
	}

	std::ostream& Element::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		this->_ptr->print(stream, level, spacesPerLevel);
		return stream;
	}

	bool Element::isNull() const { return this->_ptr->isNull(); }
	bool Element::isArray() const { return this->_ptr->isArray(); }
	bool Element::isComplexType() const { return this->_ptr->isComplexType(); }
	
	size_t Element::numValues() const { return this->_ptr->numValues(); }
	size_t Element::numElements() const { return this->_ptr->numElements(); }
	Name Element::name() const { return this->_ptr->name(); }

	int Element::datatype() const { return this->_ptr->datatype(); }

	SchemaElementDefinition Element::elementDefinition() const
	{
		return this->_ptr->elementDefinition();
	}

	bool Element::getValueAsBool(int index) const { return this->_ptr->getValueAsBool(index); }
	int Element::getValueAsInt32(int index) const { return this->_ptr->getValueAsInt32(index); }
	long Element::getValueAsInt64(int index) const { return this->_ptr->getValueAsInt64(index); }
	float Element::getValueAsFloat32(int index) const { return this->_ptr->getValueAsFloat32(index); }
	double Element::getValueAsFloat64(int index) const { return this->_ptr->getValueAsFloat64(index); }
	Datetime Element::getValueAsDatetime(int index) const { return this->_ptr->getValueAsDatetime(index); }
	const char * Element::getValueAsString(int index) const { return this->_ptr->getValueAsString(index); }
	
	Element Element::getValueAsElement(int index) const
	{
		Element result(this->_ptr->getValueAsElement(index));
		return result;
	}

	Element Element::getElement(int position) const
	{
		Element result(this->_ptr->getElement(position));
		return result;
	}
	Element Element::getElement(const char* name) const
	{
		std::shared_ptr<ElementPtr> elmP(this->_ptr->getElement(name));
		Element result(elmP);
		return result;
	}	
	Element Element::getElement(const Name& name) const
	{
		return this->getElement(name.string());
	}

	bool Element::hasElement(const char* name, bool excludeNullElements) const { return this->_ptr->hasElement(name, excludeNullElements); }
	bool Element::hasElement(const Name& name, bool excludeNullElements) const { return this->hasElement(name.string(), excludeNullElements); }
	
	bool Element::getElementAsBool(const char* name) const { return this->getElement(name).getValueAsBool(0); }
	bool Element::getElementAsBool(const Name& name) const { return this->getElementAsBool(name.string()); }
	
	int Element::getElementAsInt32(const char* name) const { return this->_ptr->getElementAsInt32(name); }
	int Element::getElementAsInt32(const Name& name) const { return this->getElementAsInt32(name.string()); }
	
	long Element::getElementAsInt64(const char* name) const { return this->getElement(name).getValueAsInt64(0); }
	long Element::getElementAsInt64(const Name& name) const { return this->getElementAsInt64(name.string()); }

	float Element::getElementAsFloat32(const char* name) const { return this->getElement(name).getValueAsFloat32(0); }
	float Element::getElementAsFloat32(const Name& name) const { return this->getElementAsFloat32(name.string()); }

	double Element::getElementAsFloat64(const char* name) const { return this->getElement(name).getValueAsFloat64(0); }
	double Element::getElementAsFloat64(const Name& name) const { return this->getElementAsFloat64(name.string()); }

	Datetime Element::getElementAsDatetime(const char* name) const { return this->getElement(name).getValueAsDatetime(0); }
	Datetime Element::getElementAsDatetime(const Name& name) const { return this->getElementAsDatetime(name.string()); }

	const char* Element::getElementAsString(const char* name) const { return this->getElement(name).getValueAsString(0); }
	const char* Element::getElementAsString(const Name& name) const { return this->getElementAsString(name.string()); }


	Element Element::appendElement()
	{
		std::shared_ptr<ElementPtr> elmP(this->_ptr->appendElement());
		Element result(elmP);
		return result;
	}

	char Element::getElementAsChar(const char* name) const { return this->_ptr->getElementAsChar(name); }
	char Element::getElementAsChar(const Name& name) const { return this->getElementAsChar(name.string()); }

	void Element::appendValue(bool value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(char value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(int value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(long long value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(float value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(double value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(const Datetime& value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(const char* value) { return this->_ptr->appendValue(value); }
	void Element::appendValue(const Name& value) { return this->_ptr->appendValue(value); }

	void Element::setElement(const char* name, const char* value) { this->_ptr->setElement(name, value); }
	void Element::setElement(const char* name, const Name& value) { this->_ptr->setElement(name, value); }
	void Element::setElement(const Name& name, const char* value) { this->_ptr->setElement(name, value); }
	void Element::setElement(const Name& name, const Name& value) { this->_ptr->setElement(name, value); }

	void Element::setElement(const char* name, int value) { this->_ptr->setElement(name, value); }
	void Element::setElement(const Name& name, int value) { this->_ptr->setElement(name, value); }

	std::string Element::toJson() const { return this->_ptr->toJson(); }
	
	const char * Element::toString(::blpapi_DataType_t datatype)
	{
		switch(datatype)
		{
			case ::BLPAPI_DATATYPE_BOOL: return "BOOL";
			case ::BLPAPI_DATATYPE_CHAR: return "CHAR";
			case ::BLPAPI_DATATYPE_BYTE: return "BYTE";
			case ::BLPAPI_DATATYPE_INT32: return "INT32";
			case ::BLPAPI_DATATYPE_INT64: return "INT64";
			case ::BLPAPI_DATATYPE_FLOAT32: return "FLOAT32";
			case ::BLPAPI_DATATYPE_FLOAT64: return "FLOAT64";
			case ::BLPAPI_DATATYPE_STRING: return "STRING";
			case ::BLPAPI_DATATYPE_BYTEARRAY: return "BYTEARRAY";
			case ::BLPAPI_DATATYPE_DATE: return "DATE";
			case ::BLPAPI_DATATYPE_TIME: return "TIME";
			case ::BLPAPI_DATATYPE_DECIMAL: return "DECIMAL";
			case ::BLPAPI_DATATYPE_DATETIME: return "DATETIME";
			case ::BLPAPI_DATATYPE_ENUMERATION: return "ENUMERATION";
			case ::BLPAPI_DATATYPE_SEQUENCE: return "SEQUENCE";
			case ::BLPAPI_DATATYPE_CHOICE: return "CHOICE";
			case ::BLPAPI_DATATYPE_CORRELATION_ID: return "CORRELATION_ID";
			default: return "default";
		}
	}
}