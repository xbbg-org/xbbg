//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/Types/CanConvertToStringType.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#pragma once

#include <string>
#include <sstream>
#include "BloombergTypes/Datetime.h"

namespace BEmu
{
	class CanConvertToStringType
	{
		private:
			std::stringstream _ss;
			std::string _valueAsString;

			void ClearStream();

		protected:
			CanConvertToStringType(int arg, bool surroundWithQuotes = false);
			CanConvertToStringType(bool arg, bool surroundWithQuotes = false);
			CanConvertToStringType(double arg, bool surroundWithQuotes = false);
			CanConvertToStringType(const std::string& arg, bool surroundWithQuotes = false);
			CanConvertToStringType(const Datetime& arg, bool surroundWithQuotes = false);
			
			//Use these to change the _valueAsString argument
			void ResetStringConversion(int arg, bool surroundWithQuotes = false);
			void ResetStringConversion(bool arg, bool surroundWithQuotes = false);
			void ResetStringConversion(double arg, bool surroundWithQuotes = false);
			void ResetStringConversion(const std::string& arg, bool surroundWithQuotes = false);
			void ResetStringConversion(const Datetime& arg, bool surroundWithQuotes = false);
			
			const std::string& ValueAsString() const;
	};
}