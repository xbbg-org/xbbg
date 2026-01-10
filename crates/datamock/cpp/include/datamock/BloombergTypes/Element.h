//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Element.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include <exception>
#include "BloombergTypes/SchemaElementDefinition.h"

namespace BEmu
{
	class Name;
	class ElementPtr;
	class Datetime;
	
	//See my explanation of the RequetPtr class in Request.h for an explanation of this class
	class Element
	{
		private:
			std::shared_ptr<ElementPtr> _ptr;

		public:
			Element(std::shared_ptr<ElementPtr> arg);

			DLL_EXPORT Element();
			DLL_EXPORT Element(const Element& arg);
			DLL_EXPORT Element& operator=(const Element &rhs);

			class ElementException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} elementEx;

			DLL_EXPORT int datatype() const;
			DLL_EXPORT SchemaElementDefinition elementDefinition() const;
			static const char * toString(::blpapi_DataType_t datatype);

			DLL_EXPORT Name name() const;
			DLL_EXPORT size_t numValues() const;
			DLL_EXPORT size_t numElements() const;
		
			DLL_EXPORT bool isNull() const;
			DLL_EXPORT bool isArray() const;
			DLL_EXPORT bool isComplexType() const;

			//The C++ version of the code doesn't have a getValue() function (Java and C# do)

			DLL_EXPORT bool getValueAsBool(int index = 0) const;
			DLL_EXPORT int getValueAsInt32(int index = 0) const;
			DLL_EXPORT long getValueAsInt64(int index = 0) const;
			DLL_EXPORT float getValueAsFloat32(int index = 0) const;
			DLL_EXPORT double getValueAsFloat64(int index = 0) const;
			DLL_EXPORT Datetime getValueAsDatetime(int index = 0) const;
			DLL_EXPORT const char* getValueAsString(int index = 0) const;
			DLL_EXPORT Element getValueAsElement(int index = 0) const;
		
			DLL_EXPORT Element getElement(int position) const;
			DLL_EXPORT bool hasElement(const char* name, bool excludeNullElements = false) const;
			DLL_EXPORT bool hasElement(const Name& name, bool excludeNullElements = false) const;
			
			DLL_EXPORT Element getElement(const char* name) const;
			DLL_EXPORT Element getElement(const Name& name) const;

			DLL_EXPORT bool getElementAsBool(const char* name) const;
			DLL_EXPORT bool getElementAsBool(const Name& name) const;

			DLL_EXPORT int getElementAsInt32(const char* name) const;
			DLL_EXPORT int getElementAsInt32(const Name& name) const;

			DLL_EXPORT long getElementAsInt64(const char* name) const;
			DLL_EXPORT long getElementAsInt64(const Name& name) const;

			DLL_EXPORT float getElementAsFloat32(const char* name) const;
			DLL_EXPORT float getElementAsFloat32(const Name& name) const;

			DLL_EXPORT double getElementAsFloat64(const char* name) const;
			DLL_EXPORT double getElementAsFloat64(const Name& name) const;

			DLL_EXPORT Datetime getElementAsDatetime(const char* name) const;
			DLL_EXPORT Datetime getElementAsDatetime(const Name& name) const;

			DLL_EXPORT const char* getElementAsString(const char* name) const;
			DLL_EXPORT const char* getElementAsString(const Name& name) const;

			DLL_EXPORT char getElementAsChar(const char* name) const;
			DLL_EXPORT char getElementAsChar(const Name& name) const;

			DLL_EXPORT std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;

			DLL_EXPORT Element appendElement();

			DLL_EXPORT void appendValue(bool value);
			DLL_EXPORT void appendValue(char value);
			DLL_EXPORT void appendValue(int value);
			DLL_EXPORT void appendValue(long long value);
			DLL_EXPORT void appendValue(float value);
			DLL_EXPORT void appendValue(double value);
			DLL_EXPORT void appendValue(const Datetime& value);
			DLL_EXPORT void appendValue(const char* value);
			DLL_EXPORT void appendValue(const Name& value);

			DLL_EXPORT void setElement(const char* name, const char* value);
			DLL_EXPORT void setElement(const char* name, const Name& value);
			DLL_EXPORT void setElement(const Name& name, const char* value);
			DLL_EXPORT void setElement(const Name& name, const Name& value);

			DLL_EXPORT void setElement(const char* name, int value);
			DLL_EXPORT void setElement(const Name& name, int value);

			DLL_EXPORT std::string toJson() const;
	};

	DLL_EXPORT inline std::ostream& operator<< (std::ostream& out, const Element& mc)
	{
		mc.print(out);
		return out;
	}
}