//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/ElementPtr.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/SchemaElementDefinition.h"
#include <exception>
#include <sstream>

namespace BEmu
{
	class ElementPtr
	{
		protected:
			void prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const std::string& value) const;
			void prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const int value) const;
			void prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const double value) const;
			void prettyPrintHelper(std::ostream& stream, int tabIndent, int spacesPerTab, const long value) const;

		public:

			virtual ~ElementPtr(); //The actual BB API does not provide a destructor

			class ElementPtrException: public std::exception
			{
				virtual const char* what() const throw()
				{
					return "My exception happened";
				}
			} elementPtrEx;

			virtual Name name() const;
			virtual size_t numValues() const;
			virtual size_t numElements() const;

			virtual int datatype() const;
		
			virtual bool isNull() const;
			virtual bool isArray() const;
			virtual bool isComplexType() const;
			virtual SchemaElementDefinition elementDefinition() const;

			//The C++ version of the code doesn't have a getValue() function

			virtual bool getValueAsBool(int index) const;
			virtual int getValueAsInt32(int index) const;
			virtual long getValueAsInt64(int index) const;
			virtual float getValueAsFloat32(int index) const;
			virtual double getValueAsFloat64(int index) const;
			virtual Datetime getValueAsDatetime(int index) const;
			virtual const char * getValueAsString(int index) const; //result good until this Element is deleted
			
			virtual std::shared_ptr<ElementPtr> getValueAsElement(int index) const;
			virtual std::shared_ptr<ElementPtr> getElement(int position) const;

			virtual bool hasElement(const char* name, bool excludeNullElements = false) const;
			bool hasElement(const Name& name, bool excludeNullElements = false) const;
			
			virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;
			std::shared_ptr<ElementPtr> getElement(const Name& name) const;

			virtual bool getElementAsBool(const char* name) const;
			bool getElementAsBool(const Name& name) const;

			virtual int getElementAsInt32(const char* name) const;
			int getElementAsInt32(const Name& name) const;

			virtual long getElementAsInt64(const char* name) const;
			long getElementAsInt64(const Name& name) const;

			virtual float getElementAsFloat32(const char* name) const;
			float getElementAsFloat32(const Name& name) const;

			virtual double getElementAsFloat64(const char* name) const;
			double getElementAsFloat64(const Name& name) const;

			virtual Datetime getElementAsDatetime(const char* name) const;
			Datetime getElementAsDatetime(const Name& name) const;

			virtual const char* getElementAsString(const char* name) const; //result good until this Element is deleted
			const char* getElementAsString(const Name& name) const; //result good until this Element is deleted

			virtual char getElementAsChar(const char* name) const;
			char getElementAsChar(const Name& name) const;

			virtual std::shared_ptr<ElementPtr> appendElement();

			virtual void appendValue(bool value);
			virtual void appendValue(char value);
			virtual void appendValue(int value);
			virtual void appendValue(long long value);
			virtual void appendValue(float value);
			virtual void appendValue(double value);
			virtual void appendValue(const Datetime& value);
			virtual void appendValue(const char* value);
			virtual void appendValue(const Name& value);

			virtual void setElement(const char* name, const char* value);
			void setElement(const char* name, const Name& value);
			void setElement(const Name& name, const char* value);
			void setElement(const Name& name, const Name& value);

			virtual void setElement(const char* name, int value);
			void setElement(const Name& name, int value);

			virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;

			// Serialize to JSON string
			virtual std::string toJson() const;
	};

	inline std::ostream& operator<< (std::ostream& out, const ElementPtr& mc)
	{
		mc.print(out);
		return out;
	}
}
