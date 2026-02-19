//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/HistoricalDataRequest/HistoricElement.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "HistoricalDataRequest/HistoricElement.h"
#include "HistoricalDataRequest/HistoricElementSecurityData.h"
#include "HistoricalDataRequest/HistoricMessage.h"
#include "BloombergTypes/Name.h"
#include <ostream>

namespace BEmu
{
	namespace HistoricalDataRequest
	{
		HistoricElement::HistoricElement(const HistoricMessage& msg) :
			_security(std::dynamic_pointer_cast<HistoricElementSecurityData>(msg.getElement("securityData")))
		{
		}

		HistoricElement::~HistoricElement()
		{
		}


		Name HistoricElement::name() const
		{
			Name result("securityData");
			return result;
		}

		size_t HistoricElement::numValues() const
		{
			return 1;
		}

		size_t HistoricElement::numElements() const
		{
			return 1;
		}

		
		bool HistoricElement::isNull() const
		{
			return false;
		}

		bool HistoricElement::isArray() const
		{
			return false;
		}

		bool HistoricElement::isComplexType() const
		{
			return true;
		}


		std::ostream& HistoricElement::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			stream << "HistoricalDataResponse (choice) = {" << std::endl;
			this->_security->print(stream, level + 1, spacesPerLevel);
			stream << '}' << std::endl;

			return stream;
		}

	}
}