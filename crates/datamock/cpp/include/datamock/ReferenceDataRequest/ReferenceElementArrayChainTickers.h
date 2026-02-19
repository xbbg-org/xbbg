//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceElementArrayChainTickers.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "ReferenceDataRequest/ReferenceElementArray.h"

namespace BEmu
{
	namespace ReferenceDataRequest
	{
		namespace OptionalityEnum
		{
			enum EnumType { put, call };
		}

		class ReferenceElementArrayChainTickers : public ReferenceElementArray
		{
			public:
				ReferenceElementArrayChainTickers(const std::string& underlier, unsigned numPoints, const std::string& strDtExp, OptionalityEnum::EnumType optionality);
				~ReferenceElementArrayChainTickers();

				virtual SchemaElementDefinition elementDefinition() const;
		};
	}
}