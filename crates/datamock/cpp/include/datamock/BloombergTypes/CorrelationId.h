//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/CorrelationId.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"

namespace BEmu
{
	class CorrelationId
	{
		public:
			enum ValueType
			{
				// The CorrelationId is unset. That is, it was created by the default CorrelationId constructor.
				UNSET_VALUE = 0,

				// The CorrelationId was created from an integer supplied by the user.
				INT_VALUE = 1,

				// The CorrelationId was created from a pointer supplied by the user.
				POINTER_VALUE = 2,

				// The CorrelationId was created internally by API.
				AUTOGEN_VALUE = 3
			};

		private:
			bool _isInternal;
			long _value;
			void * _ptr;
			int _classId;
			ValueType _valueType;

			static long _nextInternalCorrelationId; //initial correlation ID

		public:
			DLL_EXPORT CorrelationId();
			DLL_EXPORT CorrelationId(long value);
			DLL_EXPORT CorrelationId(const CorrelationId& other);
			DLL_EXPORT CorrelationId(void *value, int classId = 0);
			
			DLL_EXPORT ValueType valueType() const;
			DLL_EXPORT long long asInteger() const;
			DLL_EXPORT void * asPointer() const;

			DLL_EXPORT unsigned short classId() const;
			DLL_EXPORT CorrelationId& operator=(const CorrelationId &rhs);

			friend DLL_EXPORT std::ostream& operator<<(std::ostream& os, const CorrelationId& correlator); //needs access to _isInternal
	};

	DLL_EXPORT bool operator==(const CorrelationId& lhs, const CorrelationId& rhs);
	DLL_EXPORT bool operator!=(const CorrelationId& lhs, const CorrelationId& rhs);
	DLL_EXPORT bool operator<(const CorrelationId& lhs, const CorrelationId& rhs);
}