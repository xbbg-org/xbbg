//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/ElementPtr.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Element.h" //for blpapi_DataType_t definition
#include "BloombergTypes/ElementPtr.h"
#include "BloombergTypes/Datetime.h"
#include "Types/IndentType.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/SchemaElementDefinition.h"
#include <ostream>

namespace BEmu
{
	ElementPtr::~ElementPtr()
	{
	}

	int ElementPtr::datatype() const
	{
		return ::BLPAPI_DATATYPE_SEQUENCE;
	}

	template<typename T>
	static void prettyPrintHelperImpl(std::ostream& stream, int tabIndent, int spacesPerTab, const char* name, const T value)
	{
		std::string tabs = IndentType::Indent(tabIndent, spacesPerTab);
		stream << tabs << name << " = " << value << std::endl;
	}

	void ElementPtr::prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const std::string& value) const
	{
		prettyPrintHelperImpl(stream, tabIndent, spacesPerTab, this->name().string(), value);
	}
	
	void ElementPtr::prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const int value) const
	{
		prettyPrintHelperImpl(stream, tabIndent, spacesPerTab, this->name().string(), value);
	}
	
	void ElementPtr::prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const double value) const
	{
		prettyPrintHelperImpl(stream, tabIndent, spacesPerTab, this->name().string(), value);
	}

	void ElementPtr::prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const long value) const
	{
		std::string tabs = IndentType::Indent(tabIndent, spacesPerTab);
		stream << tabs << this->name().string() << " = " << value << std::endl;
	}

	std::ostream& ElementPtr::print(std::ostream& stream, int level, int spacesPerLevel) const
	{
		(void)stream; (void)level; (void)spacesPerLevel;
		throw elementPtrEx;
	}

	bool ElementPtr::isNull() const { return false; }
	bool ElementPtr::isArray() const { throw elementPtrEx; }
	bool ElementPtr::isComplexType() const { throw elementPtrEx; }

	SchemaElementDefinition ElementPtr::elementDefinition() const
	{
		::blpapi_DataType_t dt = (::blpapi_DataType_t)this->datatype();
		SchemaElementDefinition result(dt);
		return result;
	}
	
	size_t ElementPtr::numValues() const { throw elementPtrEx; }
	size_t ElementPtr::numElements() const { throw elementPtrEx; }
	Name ElementPtr::name() const { throw elementPtrEx; }

	bool ElementPtr::getValueAsBool(int index) const { (void)index; throw elementPtrEx; }
	int ElementPtr::getValueAsInt32(int index) const { (void)index; throw elementPtrEx; }
	long ElementPtr::getValueAsInt64(int index) const { (void)index; throw elementPtrEx; }
	float ElementPtr::getValueAsFloat32(int index) const { (void)index; throw elementPtrEx; }
	double ElementPtr::getValueAsFloat64(int index) const { (void)index; throw elementPtrEx; }
	Datetime ElementPtr::getValueAsDatetime(int index) const { (void)index; throw elementPtrEx; }
	const char * ElementPtr::getValueAsString(int index) const { (void)index; throw elementPtrEx; }
	
	std::shared_ptr<ElementPtr> ElementPtr::getValueAsElement(int index) const { (void)index; throw elementPtrEx; }
	std::shared_ptr<ElementPtr> ElementPtr::getElement(int position) const { (void)position; throw elementPtrEx; }
	std::shared_ptr<ElementPtr> ElementPtr::getElement(const char* name) const { (void)name; throw elementPtrEx; }

	std::shared_ptr<ElementPtr> ElementPtr::getElement(const Name& name) const
	{
		return this->getElement(name.string());
	}

	bool ElementPtr::hasElement(const Name& name, bool excludeNullElements) const
	{
		return this->hasElement(name.string(), excludeNullElements);
	}

	bool ElementPtr::hasElement(const char* name, bool excludeNullElements) const
	{
		(void)name; (void)excludeNullElements;
		throw elementPtrEx;
	}

	bool ElementPtr::getElementAsBool(const char* name) const
	{
		return this->getElement(name)->getValueAsBool(0);
	}

	bool ElementPtr::getElementAsBool(const Name& name) const
	{
		return this->getElementAsBool(name.string());
	}


	int ElementPtr::getElementAsInt32(const char* name) const
	{
		return this->getElement(name)->getValueAsInt32(0);
	}

	int ElementPtr::getElementAsInt32(const Name& name) const
	{
		return this->getElementAsInt32(name.string());
	}


	long ElementPtr::getElementAsInt64(const char* name) const
	{
		return this->getElement(name)->getValueAsInt64(0);
	}

	long ElementPtr::getElementAsInt64(const Name& name) const
	{
		return this->getElementAsInt64(name.string());
	}


	float ElementPtr::getElementAsFloat32(const char* name) const
	{
		return this->getElement(name)->getValueAsFloat32(0);
	}

	float ElementPtr::getElementAsFloat32(const Name& name) const
	{
		return this->getElementAsFloat32(name.string());
	}


	double ElementPtr::getElementAsFloat64(const char* name) const
	{
		return this->getElement(name)->getValueAsFloat64(0);
	}

	double ElementPtr::getElementAsFloat64(const Name& name) const
	{
		return this->getElementAsFloat64(name.string());
	}


	Datetime ElementPtr::getElementAsDatetime(const char* name) const
	{
		return this->getElement(name)->getValueAsDatetime(0);
	}

	Datetime ElementPtr::getElementAsDatetime(const Name& name) const
	{
		return this->getElementAsDatetime(name.string());
	}


	const char* ElementPtr::getElementAsString(const char* name) const
	{
		return this->getElement(name)->getValueAsString(0);
	}

	const char* ElementPtr::getElementAsString(const Name& name) const
	{
		return this->getElementAsString(name.string());
	}


	char ElementPtr::getElementAsChar(const char* name) const
	{
		(void)name;
		throw elementPtrEx;
	}

	char ElementPtr::getElementAsChar(const Name& name) const
	{
		return this->getElementAsChar(name.string());
	}


	std::shared_ptr<ElementPtr> ElementPtr::appendElement()
	{
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(bool value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(char value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(int value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(long long value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(float value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(double value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(const Datetime& value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(const char* value)
	{
		(void)value;
		throw elementPtrEx;
	}

	void ElementPtr::appendValue(const Name& value)
	{
		(void)value;
		throw elementPtrEx;
	}




	void ElementPtr::setElement(const char* name, const char* value)
	{
		(void)name; (void)value;
		throw elementPtrEx;
	}

	void ElementPtr::setElement(const char* name, const Name& value)
	{
		this->setElement(name, value.string());
	}

	void ElementPtr::setElement(const Name& name, const char* value)
	{
		this->setElement(name.string(), value);
	}

	void ElementPtr::setElement(const Name& name, const Name& value)
	{
		this->setElement(name.string(), value.string());
	}


	void ElementPtr::setElement(const char* name, int value)
	{
		(void)name; (void)value;
		throw elementPtrEx;
	}

	void ElementPtr::setElement(const Name& name, int value)
	{
		this->setElement(name.string(), value);
	}

}
