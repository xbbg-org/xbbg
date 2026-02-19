//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Constant.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Datetime.h"

namespace BEmu
{
	class Constant
	{
		public:
			DLL_EXPORT Constant(const Constant& original);

			DLL_EXPORT void setUserData(void *userData);

			DLL_EXPORT Name name() const;
			DLL_EXPORT const char *description() const;
			DLL_EXPORT int status() const;
			DLL_EXPORT int datatype() const;
			DLL_EXPORT int getValueAs(char *buffer) const;
			DLL_EXPORT int getValueAs(int *buffer) const;
			DLL_EXPORT int getValueAs(long *buffer) const;
			DLL_EXPORT int getValueAs(float *buffer) const;
			DLL_EXPORT int getValueAs(double *buffer) const;
			DLL_EXPORT int getValueAs(Datetime *buffer) const;
			DLL_EXPORT int getValueAs(std::string *buffer) const;
			DLL_EXPORT char getValueAsChar() const;
			DLL_EXPORT int getValueAsInt32() const;
			DLL_EXPORT long getValueAsInt64() const;
			DLL_EXPORT float getValueAsFloat32() const;
			DLL_EXPORT double getValueAsFloat64() const;
			DLL_EXPORT Datetime getValueAsDatetime() const;
			DLL_EXPORT std::string getValueAsString() const;
			DLL_EXPORT void *userData() const;
	};
}