//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/ReferenceDataRequest/ReferenceElementArrayChainTickersItem.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "ReferenceDataRequest/ReferenceElementArrayChainTickersItem.h"
#include "ReferenceDataRequest/ReferenceElementString.h"
#include "BloombergTypes/Name.h"
#include "Types/IndentType.h"
#include "Types/DisplayFormats.h"
#include <cstring>
#include <ostream>

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		ReferenceElementArrayChainTickersItem::ReferenceElementArrayChainTickersItem
			(const std::string& ticker, const Datetime& dtExp, ReferenceDataRequest::OptionalityEnum::EnumType optionality, int strike)
		{
			std::stringstream ss;
			ss << ticker << " US ";
			ss << DisplayFormats::ToMMddYYWithSlashes(dtExp) << ' ';

			char cp = (optionality == ReferenceDataRequest::OptionalityEnum::call) ? 'C' : 'P';
			ss << cp;

			ss << strike;
			
			this->_element = std::shared_ptr<ReferenceElementString>(new ReferenceElementString("Ticker", ss.str()));
		}

		ReferenceElementArrayChainTickersItem::~ReferenceElementArrayChainTickersItem()
		{
		}		

		Name ReferenceElementArrayChainTickersItem::name() const { return Name("Ticker"); }
		size_t ReferenceElementArrayChainTickersItem::numValues() const { return 0; }
		size_t ReferenceElementArrayChainTickersItem::numElements() const { return 1; }

		SchemaElementDefinition ReferenceElementArrayChainTickersItem::elementDefinition() const
		{
			::blpapi_DataType_t dtype = (::blpapi_DataType_t)this->datatype();
			SchemaElementDefinition result(dtype, Name("CHAIN_TICKERS"));
			return result;
		}

		bool ReferenceElementArrayChainTickersItem::isNull() const { return false; }
		bool ReferenceElementArrayChainTickersItem::isArray() const { return false; }
		bool ReferenceElementArrayChainTickersItem::isComplexType() const { return false; }

		const char* ReferenceElementArrayChainTickersItem::getElementAsString(const char* name) const
		{
			return this->getElement(name)->getValueAsString(0);
		}

		std::shared_ptr<ElementPtr> ReferenceElementArrayChainTickersItem::getElement(const char* name) const
		{
			if(strncmp(name, "Ticker", 7) == 0)
				return std::dynamic_pointer_cast<ElementPtr>(this->_element);

			else
				throw elementPtrEx;
		}

		std::ostream& ReferenceElementArrayChainTickersItem::print(std::ostream& stream, int level, int spacesPerLevel) const
		{
			std::string tabs(IndentType::Indent(level, spacesPerLevel));

			stream << tabs << "CHAIN_TICKERS = {" << std::endl;

			this->_element->print(stream, level + 1, spacesPerLevel);

			stream << tabs << '}' << std::endl;

			return stream;
		}

	}
}