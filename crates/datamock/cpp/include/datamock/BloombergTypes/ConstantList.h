//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/ConstantList.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include "bemu_headers.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/Constant.h"

namespace BEmu
{
	class ConstantList
	{
		public:
			DLL_EXPORT ConstantList(const ConstantList& original);

			DLL_EXPORT void setUserData(void *userData);
			DLL_EXPORT Name name() const;
			DLL_EXPORT const char *description() const;
			DLL_EXPORT int status() const;
			DLL_EXPORT int numConstants() const;
			DLL_EXPORT int datatype() const;
			DLL_EXPORT Constant getConstant(const Name& name) const;
			DLL_EXPORT Constant getConstant(const char *name) const;
			DLL_EXPORT Constant getConstantAt(size_t index) const;
			DLL_EXPORT void *userData() const;
	};
}