//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/bemu_headers.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

#include <memory>
#include <string>
#include <iosfwd>
#include <chrono>

#include "BloombergTypes/Datatypes.h"

#if defined _WIN32

#define DLL_EXPORT __declspec(dllexport)

#else

#define DLL_EXPORT

#endif
