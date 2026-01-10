//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceRequest.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceRequest.h"

#include "ReferenceDataRequest/ReferenceRequestElementStringArray.h"
#include "ReferenceDataRequest/ReferenceRequestElementOverrideArray.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceRequest::ReferenceRequest() :
			_securities(new ReferenceRequestElementStringArray("securities")),
			_fields(new ReferenceRequestElementStringArray("fields")),
			_overrides(new ReferenceRequestElementOverrideArray())
		{			
			this->_requestType = RequestPtr::reference;
		}

		ReferenceRequest::~ReferenceRequest()
		{
		}

		std::vector<std::string> ReferenceRequest::getSecurities() const
		{
			return this->_securities->getValues();
		}

		std::vector<std::string> ReferenceRequest::getFields() const
		{
			return this->_fields->getValues();
		}

		bool ReferenceRequest::hasElement(const std::string& arg) const
		{
			return 
				arg.compare("securities") == 0 ||
				arg.compare("fields") == 0 ||
				arg.compare("overrides") == 0;
		}

		Element ReferenceRequest::getElement(const char* name)
		{
			if(strncmp(name, "securities", 11) == 0)
				return Element(std::dynamic_pointer_cast<ElementPtr>(this->_securities));
			
			else if(strncmp(name, "fields", 7) == 0)
				return Element(std::dynamic_pointer_cast<ElementPtr>(this->_fields));
			
			else if(strncmp(name, "overrides", 10) == 0)
				return Element(std::dynamic_pointer_cast<ElementPtr>(this->_overrides));

			else
				throw requestEx;
		}

		void ReferenceRequest::append(const char* name, const char* value)
		{
			if(strncmp(name, "securities", 11) == 0)
				this->_securities->addValue(value);

			else if(strncmp(name, "fields", 7) == 0)
				this->_fields->addValue(value);

			else
				throw requestEx;
		}

		std::ostream& ReferenceRequest::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "ReferenceDataRequest = {" << std::endl;

			if(this->_securities->numValues() > 0)
				this->_securities->print(stream, level + 1, spacesPerLevel);

			if(this->_fields->numValues() > 0)
				this->_fields->print(stream, level + 1, spacesPerLevel);

			if(this->_overrides->numValues() > 0)
				this->_overrides->print(stream, level + 1, spacesPerLevel);
			
			stream << "}" << std::endl;
			return stream;
		}

	}
}