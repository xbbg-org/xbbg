//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementArray.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementArray.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementArray::ReferenceElementArray(const std::string& name, const std::vector< std::shared_ptr<ElementPtr> >& elements)
		{
			this->_name = name;
			this->_values = elements;
		}

		ReferenceElementArray::~ReferenceElementArray()
		{
			this->_values.clear();
		}

		Name ReferenceElementArray::name() const { return Name(this->_name.c_str()); }
		size_t ReferenceElementArray::numValues() const { return this->_values.size(); }
		size_t ReferenceElementArray::numElements() const { return 0; }

		bool ReferenceElementArray::isNull() const { return false; }
		bool ReferenceElementArray::isArray() const { return true; }
		bool ReferenceElementArray::isComplexType() const { return false; }

		std::shared_ptr<ElementPtr> ReferenceElementArray::getValueAsElement(int index) const
		{
			return this->_values.at(index);
		}

		std::ostream& ReferenceElementArray::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << this->_name << "[] = {" << std::endl;

			for(std::vector< std::shared_ptr<ElementPtr> >::const_iterator iter = this->_values.begin(); iter != this->_values.end(); ++iter)
			{
				std::shared_ptr<ElementPtr> elm = *iter;
				elm->print(stream, level + 1, spacesPerLevel);
			}

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}