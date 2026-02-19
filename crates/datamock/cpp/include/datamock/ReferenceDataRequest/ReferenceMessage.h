//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/ReferenceDataRequest/ReferenceMessage.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include "BloombergTypes/MessagePtr.h"
#include "Types/ObjectType.h"
#include <map>

namespace BEmu
{
	class CorrelationId;

	namespace ReferenceDataRequest
	{
		class ReferenceElementSecurityDataArray;

		class ReferenceMessage : public MessagePtr
		{
			private:
				std::shared_ptr<ReferenceElementSecurityDataArray> _securities;

			public:
				ReferenceMessage(const CorrelationId& corr, const std::map<std::string, std::map<std::string, ObjectType>>& fieldData);
				~ReferenceMessage();

				virtual std::shared_ptr<ElementPtr> getElement(const char* name) const;

				virtual const char* topicName() const;

				virtual std::shared_ptr<ElementPtr> asElement() const;

				std::shared_ptr<ElementPtr> firstElement() const;

				virtual std::ostream& print(std::ostream& stream, int level = 0, int spacesPerLevel = 4) const;
		};
	}
}